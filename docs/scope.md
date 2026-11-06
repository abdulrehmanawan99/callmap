# CallMap v1 engineering scope

Upload bounded synthetic/consented PCM WAV → durable transcription/extraction job → synchronized audio/transcript → correct and review grounded commitments/questions → export persisted reviewed action items. Cancel, delete, explicit retry, and recover interrupted workers with source/provider provenance.

The cobalt React/Vite workspace, FastAPI worker/API, PostgreSQL, Redis wakeups and private local audio remain a single-user local application. No accounts, cloud hosting, customer contact, live telephony, paid inference or mandatory diarization.

Default fixture mode accepts only the known sample fingerprint for authored results and never sends audio externally. Optional per-upload Gemini audio/text inference is implemented behind server configuration and explicit external-send consent; it has mock-contract coverage. Only `gemini-3.5-flash-lite` is allowed. Real provider compatibility and measured quality await coordinator validation with the authorized free-tier key. The development evaluation harness records zero HTTP attempts/no scores by default; independent held-out recordings and a second capable provider remain acceptance gaps. See [verification](verification.md) and [live provider setup](live-provider.md).
