# Generic Harness Helper Host

> Helper-only surface. This directory is **not** repo canon.

Canonical truth lives in:
- `AGENTS.md` (thin routing only)
- `docs/standards/01-ai-execution-system.md`
- `docs/ai-execution-system-usage-guide.md`
- `docs/knowledge/04-ai-execution-system-rationale.md`

Recommended bucket semantics:
- `templates/` — helper templates only
- `context/` — optional working context snapshots
- `specs/` — protocol-addressable specs
- `plans/` — protocol-addressable plans / test specs / TODOs
- `reports/`, `logs/`, `state/` — optional accelerator/runtime buckets

Rules:
- `.harness/` helps execution, but does not define canon.
- Protocol-only usage must still work when accelerator-only buckets are absent.
- Legacy `.omx/` content may remain temporarily as transition/history residue, but active/current docs should route to `.harness/` or canonical docs instead.

