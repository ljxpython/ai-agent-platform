# Root AGENTS Routing Surface

This root `AGENTS.md` is a **thin routing and execution-gating surface**.

It is **not** the canonical standard.

Canonical repo execution rules live in:

- `docs/standards/01-ai-execution-system.md`

Practical usage guidance lives in:

- `docs/ai-execution-system-usage-guide.md`

Background rationale lives in:

- `docs/knowledge/04-ai-execution-system-rationale.md`

Use this file to decide:

1. what to read first,
2. how to classify the task,
3. when to escalate,
4. and when direct implementation is not yet allowed.

Do **not** duplicate the full canon here.

---

## 1. Canonical Read Path

For any non-trivial task, read in this order:

1. **Root routing**
   - `AGENTS.md`
2. **Canonical repo rule**
   - `docs/standards/01-ai-execution-system.md`
3. **Practical usage**
   - `docs/ai-execution-system-usage-guide.md`
4. **Background / rationale** (only when needed)
   - `docs/knowledge/04-ai-execution-system-rationale.md`
5. **Narrowest authoritative leaf standard**
   - app/service-local docs

`.harness/` may contain plans, templates, and state, but it is **not** canonical policy. Legacy `.omx/` may remain as transition/history state only.

---

## 2. Mandatory Intake Order

Always resolve work in this order:

1. **Locus / Layer**
2. **Chain / Ownership**
3. **Standards Resolution**
4. **Execution Band**
5. **Artifacts / Verification**

Do **not** select workflow depth before locus/layer is explicit.

Do **not** implement before the governing standard path is clear.

---

## 3. Locus Resolver

### `platform-web`
- page archetype / UI composition / template choice
  - `docs/platform-web-sub2api-migration/14-frontend-development-playbook.md`
- formal control-plane page behavior
  - `apps/platform-web/docs/control-plane-page-standard.md`

### `platform-api`
- module ownership / control-plane code-shape
  - `apps/platform-api/docs/handbook/project-handbook.md`
  - `apps/platform-api/docs/handbook/development-playbook.md`
- permission / audit / operation governance
  - `apps/platform-api/docs/standards/permission-standard.md`
  - `apps/platform-api/docs/standards/audit-standard.md`
  - `apps/platform-api/docs/standards/operations-standard.md`
- runtime gateway / formal management interface
  - `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`

### `runtime-service`
- standards
  - `apps/runtime-service/runtime_service/docs/standards/*.md`
- harness checks
  - `apps/runtime-service/runtime_service/tests/harness/*.py`

### `runtime-web`
- debug-shell standard
  - `apps/runtime-web/docs/standards/runtime-web-debug-standard.md`

### `interaction-data-service`
- current API / resource / payload truth
  - `apps/interaction-data-service/docs/test-case-service-api-design.md`
- result-domain boundary / formal access chain
  - `apps/interaction-data-service/docs/standards/result-domain-boundary-standard.md`
- background design / future abstraction
  - `apps/interaction-data-service/docs/service-design.md`

### Repo-level / process / standards work
- `docs/standards/01-ai-execution-system.md`
- `docs/development-paradigm.md`
- `docs/knowledge/01-harness-engineering-foundation.md`
- `docs/knowledge/02-aitestlab-harness-blueprint.md`
- `docs/knowledge/03-harness-operating-model.md`

Always load the **narrowest authoritative leaf** that answers the current question.

---

## 4. Execution Bands

- **B1**
  - small, local, bounded, no governed surface
- **B2**
  - bounded work inside one locus or the shortest relevant chain
- **B3**
  - governed, research-heavy, contract-changing, or formal-chain work

`B1/B2/B3` are **execution bands**, not the blueprint’s Harness Layers `L1-L4`.

---

## 5. Hard Escalation Rules

Escalate out of B1 if **any** of the following is true:

- public / governed contract changes
- research is required
- formal platform behavior is affected
- runtime public contract is affected
- platform management interface is affected
- cross-service / cross-permission / cross-data boundary judgment is needed
- local proof is insufficient

When escalation is required:

1. first escalate to the relevant leaf owner / leaf doc,
2. then to the repo current-standard if needed,
3. and only then to formal-chain planning/execution.

---

## 6. Canonical Artifact Expectations

When artifacts are required, they must be compatible with the canonical grammar in:

- `docs/standards/01-ai-execution-system.md`

At minimum, think in terms of:

- Goal
- Scope
- Not-do list
- Locus / Layer
- Chain map
- Responsibility boundary / ownership split
- Standards loaded
- I/O contract
- Verification plan
- Acceptance criteria
- Retro / doc decision

Use `.harness/templates/ai-execution-system/*` as helper templates only.

---

## 7. Verification Doctrine

Always verify in this order:

1. **local / minimal proof first**
2. **shortest relevant chain second**
3. **formal chain only when required**

Do not default to full-chain validation just because it feels safer.

Do not skip local proof when the formal chain is affected.

---

## 8. Prohibitions

Do **not**:

- treat `.harness` or legacy `.omx` as canonical policy
- invent real secrets, real params, or user-owned datasets
- duplicate the full canon into `AGENTS.md`
- flatten all apps into one generic detailed standard
- select B1/B2/B3 before resolving locus/layer
- implement directly when the leaf standard path is still ambiguous

---

## 9. Completion Rule

Do not declare completion unless:

- the selected execution band is appropriate,
- the relevant leaf standard(s) were loaded,
- verification evidence exists at the required depth,
- retro/doc impact was considered,
- and no governed-surface escalation was skipped.

@RTK.md
