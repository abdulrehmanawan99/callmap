# Local v1 release notes

## 6 November 2026 — validation follow-up

- Fixed a real Gemini schema-complexity rejection while retaining complete local
  bounds, exact quotation/actor/date validation, deadlines and response limits.
- Measured the actual synthetic audio-to-review/export workflow and recorded its
  development metrics. Human corrections remain distinct from model suggestions.
- Added original independent audio/labels, fixed quality gates and reproducible
  scoring. Current service-unavailable results are retained as failures, with no
  quality claim for unrun cases.
- Added dependency attribution, static/security/secret checks and clearer service
  error handling. Data, private credentials and prior evaluation reports remain.

## Troubleshooting

Use README's dedicated ports and exact `127.0.0.1` origin. Check Docker service
health and local process ownership before starting a second launcher. Do not stop
unknown apps or delete a database volume to free a port. Enter the private local
installation token printed by the launcher; never commit or send that token.

Fixture mode accepts the exact bundled synthetic sample only. An unrelated WAV
does not receive a canned transcript. Live uploads require both server
configuration and explicit per-upload external-send consent. `Load sample` stays
offline. Missing-key, quota and temporary-provider failures are distinct from file
validation. An explicit retry may repeat earlier provider requests, so inspect the
retained attempt before retrying; no automatic retry is performed.

Only ready recordings can be reviewed/exported. An accepted action needs a manual
owner when the speech does not identify one. Export includes reviewed items only.
A version conflict means another edit won: refresh before saving again. Deletion
removes the private WAV and associated rows, but cannot erase downloads/backups or
recall a request already sent. See [threat model](threat-model.md) for boundaries.
