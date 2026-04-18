# Execution-Band Artifact Skeletons

> Helper templates only — not repo canon.

All bands keep the same repo-native grammar:
**goal, scope, not-do list, locus/layer, chain map, ownership split, standards loaded, I/O contract, verification plan, acceptance criteria, retro/doc decision**.

## B1 — Compact classification note
Use for small, bounded, local work.

```md
# B1 Artifact — <task>
- Goal: <outcome>
- Scope: <bounded change>
- Not-do list:
  - <non-goal>
- Locus / layer: <owner>
- Chain map: <local only or short boundary>
- Ownership split: <owner vs adjacent boundary>
- Standards loaded: <leaf docs/checks>
- I/O contract: <inputs/outputs/defaults/forbidden fields if relevant>
- Verification plan: <local/minimal proof>
- Acceptance criteria:
  - <must be true>
- Retro / doc decision: <none needed because... | update ...>

## TODO / Checklist
- [ ] Implement bounded change
- [ ] Run local proof
- [ ] Capture short verification note
```

## B2 — Bounded plan + TODO + verification matrix
Use for meaningful but still bounded work in one locus or a short chain.

```md
# B2 Artifact — <task>
## Goal
<outcome>

## Scope
- In: <...>
- Out: <...>

## Not-do list
- <non-goal>
- <non-goal>

## Locus / layer
- Owning locus: <...>
- Layer: <...>

## Chain map
- Shortest relevant chain: <...>
- Public/governed surface touched: <no|yes>

## Ownership split
- This locus owns: <...>
- Neighbor boundary: <...>

## Standards loaded
- <path>
- <path>

## I/O contract
- Inputs: <...>
- Outputs: <...>
- Defaults / forbidden fields / failure expectations: <...>

## Delivery plan
1. <step>
2. <step>
3. <step>

## Verification plan / matrix
| Proof level | What to run | Why it is enough |
| --- | --- | --- |
| Local/minimal | <...> | <...> |
| Shortest relevant chain | <...> | <...> |

## Acceptance criteria
- <...>
- <...>

## Retro / doc decision
- <update|none> — <reason>

## TODO breakdown
- [ ] <...>
- [ ] <...>
- [ ] <...>
```

## B3 — Governed/full artifact set
Use for governed surfaces, research-heavy design, real-input dependency, or multi-locus formal-chain work.

```md
# B3 Artifact Set — <task>
## Core artifact (PRD / plan)
- Goal: <...>
- Scope: <...>
- Not-do list:
  - <...>
- Locus / layer: <primary + adjacent loci>
- Chain map: <local, shortest chain, formal chain>
- Ownership split: <clear boundary by locus>
- Standards loaded: <authoritative leaf standards>
- I/O contract: <public inputs/outputs/defaults/forbidden fields/failure rules>
- Verification plan: <local first, shortest chain second, formal chain last if required>
- Acceptance criteria:
  - <...>
- Retro / doc decision: <docs/runbook/ADR updates>

## Additional required B3 sections
- Escalation rationale: <why B3 is required>
- Affected contract list:
  - <contract/interface/schema>
- Real-input requirements list:
  - <secret|dataset|env param|none>
- Release / handoff considerations:
  - <migration, rollout, owner, support notes>

## Companion artifacts expected
- ADR: <decision + rejected options>
- Test spec: <coverage of local, boundary, formal chain>
- Escalation log: <who/what/why>
- Real-input checklist: <link/checklist>
- Doc/runbook update plan: <what must change>
```

## Usage notes
- B1 stays compact but must still cover the grammar.
- B2 is the default for bounded meaningful delivery.
- B3 is not “large work only”; it is for governed boundaries, research, or real-input risk.
