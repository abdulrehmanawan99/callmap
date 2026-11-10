# Optional live Gemini transcription and extraction

The native provider path is implemented and tested with actual Gemini3.5 requests. [The measured development baseline](live-validation.md) records one successful synthetic API/worker workflow; general quality acceptance remains open. Default fixture mode makes no external requests. Missing configuration produces a useful failure, never a sample transcript for unrelated audio.

## Enable deliberately

1. Use a Gemini API key belonging to a **billing-disabled project** with available free-tier capacity. The app cannot inspect or enforce the project's billing tier; there is no API `free-only` flag. It never enables billing, chooses another model, or falls back to paid capacity. Quota errors fail without retry.
2. Export `GEMINI_API_KEY` securely into the API/worker environment. Keep it out of Git, browser bundles, URLs, command history, screenshots and logs. The coordinator may load the user-authorized shared environment file; this application **does not read that file automatically**. Do not paste keys into the UI.
3. Set `CALLMAP_PROVIDER=gemini` and `CALLMAP_GEMINI_MODEL=gemini-3.5-flash-lite` in the server environment or local ignored `.env`, then restart `scripts/dev.sh`. Existing `.env` settings take precedence in that script.
4. Refresh the UI, check **Send the next uploaded WAV to Gemini**, then upload consented/synthetic PCM WAV (≤10 MiB, ≤120 seconds). The checkbox resets after upload. **Load sample always remains offline fixture mode**, even if Gemini is configured. To run the sample through live inference, explicitly upload its WAV with the checkbox selected.
5. Review every model suggestion. Named `I will` speakers are not automatically identified. The model must leave ambiguous owners blank. Relative/missing-year dates retain their quoted expression with no inferred calendar date. Add owners/dates manually before accepting actions.

Removing the key or returning `CALLMAP_PROVIDER=fixture` disables new live jobs. Restart processes after configuration changes. Existing local recordings/reviews persist. A live job interrupted by worker restart becomes failed; an explicit retry may repeat already completed requests. Cancellation suppresses future stages/results when observed, but cannot undo a request already sent.

## Current official contract and execution limits

Verified from Google primary documentation on 6 November 2026:

- [Gemini 3.5 Flash-Lite](https://aistudio.google.com/docs/models/gemini-3.5-flash-lite): audio/text inputs and structured text output.
- [Audio understanding and inline data](https://aistudio.google.com/docs/audio): audio content uses `type=audio`, base64 `data`, and `mime_type=audio/wav`; inline total request cap 20 MB.
- [Structured output](https://aistudio.google.com/docs/structured-output): `response_format={type:text,mime_type:application/json,schema:…}`.
- [Interactions reference](https://ai.google.dev/api/interactions-api): POST `https://generativelanguage.googleapis.com/v1beta/interactions`, header `Api-Revision: 2026-05-20`, `x-goog-api-key`, model `gemini-3.5-flash-lite`. Read completed `steps[type=model_output].content[type=text]`; reject incomplete/blocked/invalid JSON.
- [State and retention](https://aistudio.google.com/docs/interactions): `store=false` disables interaction-state storage; this is separate from broader provider logging/data-use terms. Review [pricing/free-tier policy](https://aistudio.google.com/docs/pricing) and [API keys](https://aistudio.google.com/docs/api-key) for the actual project before sending data.

The user authorizes only `gemini-3.5-flash-lite`; the adapter rejects every other model ID before HTTP. It uses `thinking_level=minimal`, the model's documented default for extraction ([migration guidance](https://aistudio.google.com/docs/whats-new-gemini-3.6#migrate-to-gemini-3-5-flash-lite)). The adapter pins this model only, with no arbitrary endpoint/model or tool configuration. Each attempt uses at most two HTTP requests, each with ≤16 MiB encoded JSON, 6,000 maximum output tokens, and ≤512 KiB response bytes. Each request has a 65-second asynchronous network deadline covering connection, upload, response headers and body streaming; the connect timeout is 10 seconds and read/write/pool inactivity timeouts are 60 seconds within that total deadline. Deadline cancellation closes the owned HTTP client. Bounded local JSON encoding/validation and connection cleanup add small local overhead outside that network deadline; this is not a whole-job latency SLA. No retries, redirects, environment proxy, remote file storage, conversation continuation or paid fallback. Transcript ≤80 segments/20,000 characters; extraction ≤30 suggestions; strict bounded fields, exact quotation and segment checks. Invalid outputs fail the job for explicit retry; no canned substitute is used.

Serving schemas omit numeric/length/array/format bounds that caused an actual HTTP400 state-complexity rejection. Object structure and enums remain in the request. Full bounds and formats are validated locally before publication; invalid outputs fail, never silently truncate.

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

[Historical blocked report](live-evaluation-blocked.json) records the earlier no-call state. [Current measured baseline](live-validation.md) records actual compatibility and development scores. Review failure cases and set numeric thresholds before broader quality claims; use independent consented/synthetic recordings for those claims. A second authorized speech/text configuration remains unimplemented/unverified. Mock contract tests prove HTTP shape, validation, grounding, error and publication mechanics, not model capability or quality.

The [independent synthetic evaluation](independent-validation.md) froze gates and three new labeled recordings before inference. Its first request returned HTTP503; execution stopped after one request, with no independent quality scores or retries. The remaining cases are preserved for a future bounded run after provider availability changes; the user's exact-model synthetic-test authorization persists.

A later [bounded resume](independent-validation.md#bounded-resume-after-availability-recovered) made three HTTP200 requests: the negative case returned zero commitments but failed the frozen lexical timestamp metric on split segmentation; the next transcript failed local ordering/ID/timestamp validation, and the final case was not attempted. Independent quality acceptance remains open; no labels or gates were retuned.

A source-restricted diagnostic proved a sub-millisecond prompt-rounding mismatch: measured WAV length5.055600907s was formatted as5.056s, and the model used exactly that displayed end. The validator now canonicalizes only an end overrun of **at most0.0005s** back to measured duration, then rechecks ordering and nonempty intervals. Larger overruns, invalid IDs and overlapping/reversed segments still fail. Numeric speech-quality gates remain unchanged.
