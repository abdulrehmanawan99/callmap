# CallMap agent guidance

- This is a standalone GitHub portfolio project in `/Users/apple/Desktop/callmap`.
- Read `/Users/apple/Desktop/AGENTS.md` and `docs/scope.md` before work.
- Work only in this repository; the active batch is EvidenceLens, Webhook Clinic,
  and CallMap. Do not change the other repositories or shared orchestration files.
- Keep one complete v1 workflow focused, polished, and understandable. Avoid
  speculative services, generic frameworks, hosted identity, or multitenancy.
- Stack: React/Vite + TypeScript, FastAPI API/worker, PostgreSQL, Redis, private local audio storage.
- Preserve the distinct interface direction. Include loading/error/empty states,
  keyboard access, responsive layout, and a clear fixture-mode label.
- Use synthetic data. Validate inputs and bound external work. Keep secrets out
  of source, logs, and browser bundles. Do not expose services beyond loopback.
- No paid model calls, model downloads, external messages, deployment, GitHub
  publication, or remote push. Existing coding-agent access is for development,
  not an application inference provider.
- Do not invent live AI acceptance, screenshots, tests, or implementation status.
- Add focused domain/integration checks, reproducible setup, and locked dependencies.
- Use dedicated ports and project-specific volumes; do not stop unknown services
  or touch EvidenceLens data, ports, artifacts, or database containers.
- Report changed files, actual checks, blockers, and next steps to the orchestrator.
- Do not spawn further agents. Local commits are allowed; no amend or force push.
