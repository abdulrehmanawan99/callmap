import base64
from datetime import date
import json

import httpx
import pytest

from api.providers import (
    API_REVISION,
    ENDPOINT,
    MAX_RESPONSE_BYTES,
    Commitment,
    Extraction,
    Gemini,
    ProviderError,
    Transcript,
    explicit_date,
    generation_schema,
)
from api.tests.test_core import wav

TEXT = "Maya will send the checklist by November twelfth, twenty twenty six."
TRANSCRIPT = {
    "segments": [
        {"id": 0, "start": 0.0, "end": 0.9, "speaker": "Speaker 1", "text": TEXT}
    ]
}
ITEM = {
    "segment_id": 0,
    "text": "Send the checklist",
    "source_quote": TEXT,
    "owner": "Maya",
    "owner_evidence": TEXT,
    "due_date": "2026-11-12",
    "date_expression": "November twelfth, twenty twenty six",
    "kind": "action",
}


def reply(value):
    return {
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": json.dumps(value)}],
            }
        ],
        "usage": {
            "total_input_tokens": 20,
            "total_output_tokens": 10,
            "unexpected": "not retained",
        },
    }


@pytest.fixture
def live_env(monkeypatch):
    monkeypatch.setenv("CALLMAP_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-never-real")
    monkeypatch.setenv("CALLMAP_GEMINI_MODEL", "gemini-3.5-flash-lite")


def test_native_interactions_audio_then_grounded_text_contract(live_env):
    calls = []

    def handler(request):
        assert str(request.url) == ENDPOINT
        assert request.headers["Api-Revision"] == API_REVISION
        assert request.headers["x-goog-api-key"] == "test-key-never-real"
        body = json.loads(request.content)
        calls.append(body)
        assert (
            body["store"] is False
            and body["generation_config"]["max_output_tokens"] == 6000
        )
        assert body["response_format"]["mime_type"] == "application/json"
        assert body["model"] == "gemini-3.5-flash-lite"
        assert body["generation_config"]["thinking_level"] == "minimal"
        if len(calls) == 1:
            assert base64.b64decode(body["input"][1]["data"]) == wav()
            assert body["input"][1]["mime_type"] == "audio/wav"
            return httpx.Response(200, json=reply(TRANSCRIPT))
        assert len(body["input"]) == 1 and TEXT in body["input"][0]["text"]
        return httpx.Response(200, json=reply({"commitments": [ITEM]}))

    provider = Gemini(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    transcript = provider.transcribe(wav(), 1)
    result = provider.extract(transcript)
    assert result.commitments[0].due_date == date(2026, 11, 12)
    assert len(calls) == 2 and len(provider.usage) == 2
    assert "unexpected" not in provider.usage[0]


def test_serving_schema_omits_state_exploding_bounds_but_local_validation_keeps_them(live_env):
    calls = []

    def handler(request):
        schema = json.loads(request.content)["response_format"]["schema"]
        assert schema == generation_schema(Transcript.model_json_schema())
        segment = schema["$defs"]["Segment"]
        assert segment["properties"]["id"]["type"] == "integer"
        assert segment["additionalProperties"] is False
        assert "id" in segment["required"]
        assert "maxItems" not in schema["properties"]["segments"]
        assert "maximum" not in segment["properties"]["id"]
        assert "maxLength" not in segment["properties"]["text"]
        calls.append(1)
        invalid = {"segments": [dict(TRANSCRIPT["segments"][0], text="x" * 2001)]}
        return httpx.Response(200, json=reply(invalid))

    provider = Gemini(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError, match="typed output contract"):
        provider.transcribe(wav(), 1)
    assert len(calls) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503, 302])
def test_errors_are_secret_free_and_not_retried(live_env, status):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(
            status, json={"error": "private transcript test-key-never-real"}
        )

    provider = Gemini(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError) as error:
        provider.transcribe(wav(), 1)
    assert len(calls) == 1
    assert "private transcript" not in str(error.value) and "test-key" not in str(
        error.value
    )
    if status == 503:
        assert "temporarily unavailable" in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"status": "incomplete", "steps": []}),
        httpx.Response(
            200,
            json=reply(
                {
                    "segments": [
                        {"id": 0, "start": 0, "end": 100, "speaker": "x", "text": "x"}
                    ]
                }
            ),
        ),
        httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1)),
        httpx.Response(200, json=reply({"segments": []})),
        httpx.Response(
            200, json=reply({"segments": [dict(TRANSCRIPT["segments"][0], id=1)]})
        ),
        httpx.Response(200, content=b"private malformed response"),
    ],
)
def test_incomplete_invalid_oversized_outputs_are_rejected(live_env, response):
    provider = Gemini(httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)))
    with pytest.raises(ProviderError):
        provider.transcribe(wav(), 1)


def test_timeout_is_sanitized(live_env):
    def handler(request):
        raise httpx.ReadTimeout("secret test-key-never-real", request=request)

    provider = Gemini(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError, match="transport"):
        provider.transcribe(wav(), 1)


@pytest.mark.parametrize(
    "patch",
    [
        {"segment_id": 4},
        {"source_quote": "fabricated promise"},
        {"owner": "Leo", "owner_evidence": TEXT},
        {"due_date": "2026-11-13"},
        {"date_expression": "tomorrow", "due_date": "2026-11-12"},
    ],
)
def test_commitments_need_source_owner_and_absolute_date_evidence(patch):
    transcript = Transcript.model_validate(TRANSCRIPT)
    with pytest.raises(ProviderError):
        Extraction(commitments=[Commitment.model_validate(ITEM | patch)]).ground(
            transcript
        )


def test_recipient_is_not_accepted_as_owner():
    text = "I will send the checklist to Maya tomorrow."
    transcript = Transcript.model_validate(
        {"segments": [TRANSCRIPT["segments"][0] | {"text": text}]}
    )
    item = ITEM | {
        "source_quote": text,
        "owner_evidence": text,
        "date_expression": "tomorrow",
        "due_date": None,
    }
    with pytest.raises(ProviderError, match="actor"):
        Extraction(commitments=[Commitment.model_validate(item)]).ground(transcript)


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("2026-11-12", date(2026, 11, 12)),
        ("November twelfth, twenty twenty six", date(2026, 11, 12)),
        ("November 12th, 2026", date(2026, 11, 12)),
        ("tomorrow", None),
        ("next Friday", None),
        ("November twelfth", None),
        ("February thirtieth 2026", None),
    ],
)
def test_explicit_dates_only(phrase, expected):
    assert explicit_date(phrase) == expected


def test_default_fixture_cannot_send_even_with_key(monkeypatch):
    monkeypatch.setenv("CALLMAP_PROVIDER", "fixture")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with pytest.raises(ProviderError, match="not enabled"):
        Gemini()


def test_missing_key_and_oversized_inline_audio_do_not_call(live_env, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ProviderError, match="missing"):
        Gemini()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-never-real")

    def forbidden(request):
        raise AssertionError("No request should be made.")

    from api.providers import MAX_LIVE_BYTES

    provider = Gemini(httpx.AsyncClient(transport=httpx.MockTransport(forbidden)))
    with pytest.raises(ProviderError, match="10 MiB"):
        provider.transcribe(bytes(MAX_LIVE_BYTES + 1), 120)
    monkeypatch.setenv("CALLMAP_GEMINI_MODEL", "unapproved-model")
    with pytest.raises(ProviderError, match="Unsupported"):
        Gemini()


def test_evaluation_wer_counts_insertions_deletions_and_substitutions():
    from scripts.evaluate_live import wer

    assert wer(["one", "two"], ["one", "three"]) == 0.5
    assert wer(["one", "two"], ["one"]) == 0.5
    assert wer(["one"], ["one", "extra"]) == 1


def test_total_deadline_cancels_stalled_response_headers(live_env, monkeypatch):
    import asyncio
    from api import providers

    monkeypatch.setattr(providers, "REQUEST_DEADLINE_SECONDS", 0.01)
    cancelled = []

    async def handler(request):
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        raise AssertionError("The total deadline should cancel the header wait")

    provider = Gemini(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError, match="deadline"):
        provider.transcribe(wav(), 1)
    assert cancelled == [True] and provider.http_attempts == 1


@pytest.mark.parametrize("model", ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-lite-latest"])
def test_only_exact_authorized_model_is_accepted(live_env, monkeypatch, model):
    monkeypatch.setenv("CALLMAP_GEMINI_MODEL", model)
    with pytest.raises(ProviderError, match="Unsupported"):
        Gemini()
