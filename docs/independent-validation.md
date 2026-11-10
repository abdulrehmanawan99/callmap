# Independent synthetic evaluation — 6 November 2026

Independent quality acceptance is **not achieved**. The [final bounded run](#final-bounded-run) measured all three cases: **2 of 3 pass** the frozen gates and the named-owner/date case fails strict WER and owner checks. Earlier attempts (an HTTP503, then a validation stop) remain recorded below. This does not replace the earlier successful [development baseline](live-validation.md).

## Frozen plan and sources

Commit `31f1d6b` froze [numeric gates](../fixtures/independent/gates.json) **before generating the audio or making inference requests**. The prior development result (WER 0.1444, mean boundary error 0.251 seconds) informed these limits:

- Each recording: normalized token WER ≤0.25; mean timestamp boundary error ≤0.75 seconds and every individual boundary error ≤1.5 seconds.
- Exact keyword/kind extraction precision and recall 1.0, all expected owner/date values correct, and zero false commitments on the negative case.
- Relative dates remain null calendar dates and ambiguous first-person speakers remain unassigned. No invented named owner or absolute date is acceptable.

Commit `e017551` froze the original [corpus manifests and WAVs](../fixtures/independent/corpus.json) before their first live request. These are distinct from the authored development recording: background statements with no commitments; a named actor and fully explicit date; and an unnamed first-person commitment plus an unresolved question with relative dates. Local macOS `say` (Samantha, 170 wpm) and `afconvert` produced mono 22.05 kHz 16-bit PCM. The manifests retain original text, exact SHA-256, expected items and measured synthesized-utterance boundaries. They are prospective independent synthetic cases, not a representative human-speech benchmark.

WER keeps literal normalized tokens, so spoken words versus numeric date formatting can increase it even when the date means the same thing. That is reported, never normalized away after seeing an output. Timestamp alignment uses lexical segment overlap and requires manual inspection of split/merged utterances. For zero expected items and zero predictions, precision/recall are defined as 1; a separate exact-zero-prediction check enforces the negative case.

## Initial bounded attempt (preserved history)

The existing private API and measured worker were checked to belong to CallMap and report exact `gemini-3.5-flash-lite`; there were no pending jobs. One explicit `provider=gemini` upload sent the 6.131-second `background-only` synthetic WAV. Its **first transcription request returned HTTP503 `service_unavailable` / high demand** after 4.694 seconds of app time. The worker marked it failed with no transcript, commitments or usage. Provider token usage is unknown, not zero.

The run stopped immediately. **One new generation request occurred**, below the six-request maximum. Extraction and both remaining recordings were not attempted; no automatic/manual retry, alternative model, key change or billing change followed. The failed synthetic recording remains in the local library. Raw private observations remain under ignored `.local/independent-*`; no secret, raw provider error body or key is committed.

[Machine-readable gate report](independent-evaluation.json) records zero measured cases out of three, the first pipeline failure, two explicitly not-attempted cases and `quality_acceptance=not_established`. A failed availability check is not a failed or passed speech-quality measurement. The predeclared labels and gates remain unchanged.

## Reproduce without spending quota

```sh
# Default is offline: lists pending/previously attempted cases, makes no HTTP request.
.venv/bin/python -m scripts.evaluate_independent
# Offline scoring reads already persisted API results; makes no provider call. Exit 2 is expected while cases are unmeasured.
.venv/bin/python -m scripts.score_independent \
  --results .local/independent-api-results.json \
  --output .local/independent-gates.json
```

The runner's explicit `--allow-external-synthetic-audio` flag expresses deliberate external-send intent. Resume only after service availability changes, with a documented bounded request budget. It uses only the fixed loopback API and existing server-side exact-model configuration. It checkpoints the recording ID before polling, skips every previously attempted case (including failures), waits at most 140 seconds per job, and stops on the first failure/cancellation. It never retries or resets the saved results. Retain the same results file; changing/removing it can lose the record of prior external sends. This attempt stopped at its first service failure and schedules no further calls. A future bounded run must retain these results and must not automatically retry the failed case.

Scorer exit codes are **0** when every measured case passes all gates, **1** for any measured quality failure (even if other cases remain unmeasured), and **2** when acceptance is not established with no measured failure and incomplete coverage. All outcomes still write their report. Exact source checks require an existing integer segment ID and a nonblank string quotation contained in that segment; negative or boolean IDs and malformed quotations fail the check.

## Bounded resume after availability recovered

After an availability probe returned HTTP200, a new private session guard allowed at most **six additional requests** on the same exact model. Prior results/reports were copied and preserved. The failed background recording was explicitly retried **once using the same recording ID**, with no duplicate upload. The existing runner then uploaded only the still-unattempted named-calendar case.

[Current machine-readable execution and gate report](independent-resume.json) records **three new HTTP200 responses**, four cumulative independent requests including the initial HTTP503, and these outcomes:

- Background-only completed two stages in **3.641 seconds**, with two transcript segments and **zero commitments**. WER was **0.0**, and the zero-prediction precision/recall convention gave **1.0/1.0**. The frozen lexical timestamp scorer matched the single two-sentence reference span to just the first model segment: mean boundary error **1.381s**, worst boundary error **2.761s**, so both timestamp gates **failed**. Comparing the complete two-segment output span with the reference gives an end difference of **0.289s**; this explains the segmentation limitation but does not change the official score or establish a gate pass. No audio-listening or diarization claim is made.
- Named-calendar transcription returned HTTP200 but failed the local `ordering, IDs, or timestamps` validator. No transcript or commitments were published; extraction was never called. The invalid candidate was not retained, so the precise rejected field is unknown. This is a provider-output validation failure, not an HTTP availability failure or an extraction-quality measurement.
- Relative-open remains **not attempted** because the runner stopped at the first pipeline failure. No failed/successful case was repeated to improve a score.

Reported usage for all three resumed requests was **785 input / 228 output / 0 thought tokens**; request times were **2.239s, 1.114s and 2.054s**. The first two account for the background result; the third belongs to the rejected named-calendar transcript. Usage for the earlier HTTP503 remains unknown. The private guard is stopped after this session; no further calls are scheduled.

The latest scorer exits **1** for a measured frozen-gate failure, with **1/3 cases measured**, one pipeline validation failure and one not-attempted case. At the end of that run, labels, gates, source WAVs and the v1 scoring logic were unchanged. The versioned evaluator fix below retains this original failure rather than silently relabeling it.

The HTTP503 UI error is now a fixed actionable temporary-unavailability message, with a regression proving one request and no retry. Offline scorer checks cover empty ground truth, invented owners/dates, unmeasured cases and source fingerprints. Broader quality, noisy speech, diarization and a second provider remain unverified; a second provider is out of scope for v1.

## Versioned timestamp metric correction

A minimal evaluator bug fix was made after observing the split-segmentation failure. [Metric v2](../fixtures/independent/metric-v2.json) is frozen before any inference on the still-unseen relative-open case. It chooses the best **contiguous span** of model segments using the same normalized-word-set lexical overlap, preferring shorter then earlier spans on ties; it compares the first start and last end. It never invents internal word timings when one model segment merges multiple reference utterances. Split and merged-segment regressions cover both behaviors. Numeric thresholds, source labels and WAV hashes remain unchanged.

The original [v1 failure](independent-resume.json) remains immutable historical evidence. [Offline v2 regression report](independent-v2-regression.json) uses the already persisted output, with **no new calls**: background WER0, zero false commitments, mean boundary error0.144s and end error0.289s pass the unchanged thresholds. This post-hoc correction is **seen-data regression evidence, not a fresh held-out pass**. Only1/3 cases is measured, so acceptance remains not established and the v2 scorer exits2. To reproduce v1, pass `--timestamp-metric lexical-single-segment-v1`; independent scoring defaults to the versioned contiguous-span v2.

Transcript failures now distinguish fixed non-secret reasons for non-consecutive IDs, overlapping/unordered timestamps, and an end beyond measured WAV duration. No duration tolerance or validation bound was loosened. A separately bounded named-calendar diagnostic will inspect only its committed synthetic source if explicitly resumed; raw candidate capture is restricted by its exact WAV SHA-256 and kept private.

## Exact-source named-calendar diagnostic

One additional explicitly bounded transcription retry on the same named-calendar record returned HTTP200. A private wrapper retained parsed transcript content **only after the inline WAV hash matched the committed named-calendar SHA-256**; its output file is0600 and contains neither provider envelope nor key. It made no extraction request. Actual WAV duration was **5.055600907s**, the prompt displayed **5.056s**, and the model returned an end of **5.056s**: an overrun of **0.000399093s**. The more precise validator identified outside-duration rather than an ID/order error. Diagnostic usage was246 input/83 output/0 thought tokens, provider2.706s and app3.129s.

This proves a rounding mismatch introduced by the three-decimal prompt duration. The fix canonicalizes **only** `0 < end - measured_duration <= 0.0005` seconds to exact measured duration and then rechecks all ordering/nonempty/end bounds. Larger errors still reject. Regressions cover this captured duration, too-large overruns, and a start that would become invalid after clamping. No quality threshold or source label changed. The existing captured response validates offline after this fix; that check made no new call. A separate budget capped the final named retry plus unseen relative case at four further HTTP requests; prior reports remain intact.

## Final bounded run

Within that four-request cap, the named-calendar retry and the unseen relative-open case completed (four HTTP200 responses, no retries). All three cases are now measured with the unchanged v1 gates and the frozen v2 timestamp metric. [Persisted API results](independent-final-results.json) and the [offline gate report](independent-final.json) are committed; rescoring makes no HTTP request:

```sh
.venv/bin/python -m scripts.score_independent \
  --results docs/independent-final-results.json --output .local/independent-final.json
```

| Case | Result | Notes |
| --- | --- | --- |
| background-only | pass | WER 0, zero false commitments, mean boundary error 0.144s |
| relative-open | pass | WER 0, 2/2 items, relative dates kept unresolved, mean boundary error 0.09s |
| named-calendar | **fail** | WER 0.4167 (> 0.25) and owner mismatch: the model wrote "Norah" and "December 7th, 2026" for the spoken "Nora" / "December seventh, twenty twenty six". The date and action matched. |

The scorer exits **1** (`quality_acceptance=failed_frozen_gates`). No label, gate or metric was changed after seeing these outputs. Three short synthetic recordings are not a representative benchmark.
