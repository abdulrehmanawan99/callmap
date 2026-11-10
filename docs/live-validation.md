# Live Gemini development validation — 6 November 2026

The API/worker workflow completed on exact `gemini-3.5-flash-lite`, using the
bundled 33.79-second synthetic WAV and explicit per-upload consent. The native
Interactions endpoint produced six transcript segments and four grounded
commitments in two requests. The final successful app attempt took6.225seconds;
provider times were3.707/1.953seconds. Usage was1449 input and925 output tokens,
zero reported thought tokens. No alternate model, automatic retry or replay,
billing change, or hosted embedding request was used.

The initial adapter failed before transcription: HTTP400 `invalid_request`,
because the nested schema bounds produced too many serving states. The wire
schema now keeps object/types/required fields/enums and omits numeric, length,
array-size and format constraints. Full Pydantic bounds, the response byte cap,
timestamp ordering, exact source quotations, explicit actor/date evidence, and
local processing limits still reject invalid results. A regression proves an
oversized transcript is rejected despite the simpler serving schema. The
Interactions endpoint and model were not changed.

There were five known HTTP attempts across the original failure, diagnostic
attempt, explicit measured failure and final successful two-stage run. The
original diagnostic harness failed during cross-event-loop client cleanup before
retaining its observed status; no status or quality result is attributed to it.
The corrected ignored harness saves bounded sanitized status before cleanup and
closes its client on the request's event loop. No raw audio/key/provider error body
is committed. There are no automatic provider retries.

## Observed development results

[Machine-readable measurement](live-development.json) was scored locally from the
persisted API result; scoring made no additional provider requests.

- Normalized token word error rate:14.44%. Date formatting (spoken words versus
  numeric dates) affects this metric; it is not a semantic accuracy percentage.
- Exact keyword/kind matching:4/4 expected commitments,4 predictions;
  precision1.0/recall1.0 on this single authored development recording.
- All four owner/date expectations matched, including the question's null date.
  The three fully explicit calendar dates were accepted. Ambiguous speakers'
  owners stayed blank; the recipient Maya was not inferred to own an action.
- Mean lexically aligned timestamp boundary error:0.251seconds. Individual boundary
  errors and the matching method are included in the JSON report.
- All four suggestions passed exact quotation checks. Source quotations refer to
  model-produced transcript text, which still requires comparison with the audio.
- Actual review/export endpoints rejected an action with no owner. A synthetic
  manual assignment (`Demo assignee`) was then saved and the reviewed-only export
  contained exactly that one item with live model/source provenance. The other
  three suggestions stayed unreviewed; the assignment is not an inferred identity.

The sample is a development fixture, not an independent held-out recording.
Neither general quality acceptance nor diarization/two-provider coverage is
claimed. A second provider is out of scope for v1.
The completed synthetic recording remains in the local app for inspection.
The earlier [blocked report](live-evaluation-blocked.json) is historical no-call
harness evidence, superseded for compatibility by this measured baseline.

## Independent follow-up

A [prospective three-case corpus and frozen gates](independent-validation.md) were added after this baseline. The first new transcription request returned HTTP503 high demand and the run stopped after one request; two cases remain unattempted. No independent quality pass or extra baseline score is claimed.

The subsequent [bounded independent resume](independent-validation.md#bounded-resume-after-availability-recovered) measured one case but did not pass the frozen gates and stopped on the next transcript validation failure. The earlier baseline remains development evidence, not a general acceptance claim.
