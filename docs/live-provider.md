# Optional live Gemini transcription and extraction

The native provider path is implemented and mock-HTTP tested. **No live call or quality pass is claimed.** Default fixture mode makes no external requests. Missing configuration produces a useful failure, never a sample transcript for unrelated audio.

## Enable deliberately

1. Use a Gemini API key belonging to a **billing-disabled project** with available free-tier capacity. The app cannot inspect or enforce the project's billing tier; there is no API `free-only` flag. It never enables billing, chooses another model, or falls back to paid capacity. Quota errors fail without retry.
2. Export `GEMINI_API_KEY` securely into the API/worker environment. Keep it out of Git, browser bundles, URLs, command history, screenshots and logs. The coordinator may load the user-authorized shared environment file; this application **does not read that file automatically**. Do not paste keys into the UI.
3. Set `CALLMAP_PROVIDER=gemini` and `CALLMAP_GEMINI_MODEL=gemini-3.8-flash` in the server environment or local ignored `.env`, then restart `scripts/dev.sh`. Existing `.env` settings take precedence in that script.
4. Refresh the UI, check **Send the next uploaded WAV to Gemini**, then upload consented/synthetic PCM WAV (≤10 MiB, ≤120 seconds). The checkbox resets after upload. **Load sample always remains offline fixture mode**, even if Gemini is configured. To run the sample through live inference, explicitly upload its WAV with the checkbox selected.
5. Review every model suggestion. Named `I will` speakers are not automatically identified. The model must leave ambiguous owners blank. Relative/missing-year dates retain their quoted expression with no inferred calendar date. Add owners/dates manually before accepting actions.

Removing the key or returning `CALLMAP_PROVIDER=fixture` disables new live jobs. Restart processes after configuration changes. Existing local recordings/reviews persist. A live job interrupted by worker restart becomes failed; an explicit retry may repeat already completed requests. Cancellation suppresses future stages/results when observed, but cannot undo a request already sent.

## Current official contract and execution limits

Verified from Google primary documentation on 5 November 2026:

- [Gemini 3.8 Flash](https://aistudio.google.com/docs/models/gemini-3.8-flash): audio/text inputs and structured text output.
- [Audio understanding and inline data](https://aistudio.google.com/docs/audio): audio content uses `type=audio`, base64 `data`, and `mime_type=audio/wav`; inline total request cap 20 MB.
- [Structured output](https://aistudio.google.com/docs/structured-output): `response_format={type:text,mime_type:application/json,schema:…}`.
- [Interactions reference](https://ai.google.dev/api/interactions-api): POST `https://generativelanguage.googleapis.com/v1beta/interactions`, header `Api-Revision: 2026-05-20`, `x-goog-api-key`, model `gemini-3.8-flash`. Read completed `steps[type=model_output].content[type=text]`; reject incomplete/blocked/invalid JSON.
- [State and retention](https://aistudio.google.com/docs/interactions): `store=false` disables interaction-state storage; this is separate from broader provider logging/data-use terms. Review [pricing/free-tier policy](https://aistudio.google.com/docs/pricing) and [API keys](https://aistudio.google.com/docs/api-key) for the actual project before sending data.

The adapter pins this model only, with no arbitrary endpoint/model or tool configuration. Each attempt uses at most two HTTP requests, each with ≤16 MiB encoded JSON, 6,000 maximum output tokens, and ≤512 KiB response bytes. HTTP connect timeout is 10 seconds, read/write inactivity timeout is 60 seconds; an elapsed-time guard is checked at response chunks after 65 seconds (a stalled chunk can additionally consume the read timeout). These are bounded local execution limits, not a latency SLA. No retries, redirects, environment proxy, remote file storage, conversation continuation or paid fallback. Transcript ≤80 segments/20,000 characters; extraction ≤30 suggestions; strict bounded fields, exact quotation and segment checks. Invalid outputs fail the job for explicit retry; no canned substitute is used.

Current named-owner validator deliberately supports explicit actor forms (`Maya will`, `Maya agreed to`, `Maya is going to`, `Maya: I will`) and may reject other valid phrasings. Numeric ISO/English dates are explicit; spelled-out English years 2020–2039 are supported. This conservative contract trades recall for reviewability and requires live baseline testing.

## Development evaluation (no invented scores)

`fixtures/live-evaluation.json` labels the bundled synthetic audio. It is a **development dataset, not held out**. Authored fixture UI owner names are not live identity labels; the speakers do not identify themselves in the WAV, so live expected owners are blank.

```sh
# Safe default: no calls, writes a blocked report.
.venv/bin/python -m scripts.evaluate_live
# Only after explicit authorization and billing-disabled key setup:
CALLMAP_PROVIDER=gemini .venv/bin/python -m scripts.evaluate_live \
  --allow-external-synthetic-audio --output .local/live-evaluation.json
```

The harness verifies the source fingerprint, makes only the two pipeline calls, and measures normalized-word Levenshtein WER, explicit keyword/kind extraction precision/recall, date/owner agreement, lexical timestamp alignment error, token usage and elapsed time. Matching is transparent and approximate: segmentation, paraphrases and speech normalization need manual review. The report does not store keys, raw responses, or actual model transcript. A contract/provider error produces a sanitized blocked report. `live_http_attempts` counts calls entering the HTTP transport, including quota/transport failures; configuration/preflight failures count zero. It cannot prove the provider received or completed a request.

[Current blocked report](live-evaluation-blocked.json) records **zero live calls and no scores**. Establish a real development baseline, review failure cases and set numeric thresholds afterward; add independent held-out consented/synthetic recordings before acceptance. A second authorized speech/text configuration remains unimplemented/unverified. Mock contract tests prove HTTP shape, validation, grounding, error and publication mechanics, not model capability or quality.
