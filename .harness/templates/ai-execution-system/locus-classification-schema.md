# Locus Classification Schema

> Helper template only — not repo canon.

## When to use
Use before choosing B1/B2/B3. Intake order is:
1. classify locus/layer/ownership,
2. load narrow standards,
3. map the affected chain,
4. then pick the lightest safe execution band.

## Quick routing guide
- **B1** — small, bounded, local to one locus, no governed contract change, no research, no real-input dependency.
- **B2** — meaningful but bounded work in one locus or a short nearby chain.
- **B3** — governed/public contract work, research-heavy design, real-input dependency, or multi-locus formal-chain work.

## Intake template
```md
## Locus Classification
- Goal: <one-sentence outcome>
- Scope: <what is being changed>
- Not-do list:
  - <explicit non-goal>
  - <explicit non-goal>

## Locus / Layer
- Owning locus: <repo|platform frontend|platform api|runtime|data|other>
- Layer: <blueprint/harness layer name>
- Why this is the owner: <1 line>

## Chain Map
- Local only / shortest relevant chain / formal chain: <pick one>
- Upstream touched: <none|...>
- Downstream touched: <none|...>
- Governed/public surface involved: <no|yes — which one>

## Ownership Split
- This locus owns: <responsibility>
- Adjacent loci own: <responsibility kept elsewhere>
- Must not be pulled across boundary: <boundary rule>

## Standards Loaded
- Primary leaf standard(s):
  - <path>
- Secondary supporting standard(s):
  - <path or none>

## Execution Band Recommendation
- Recommended band: <B1|B2|B3>
- Why not lower: <1 line>
- Why not higher: <1 line>
- Escalation trigger present: <none|contract|research|formal chain|real input|multi-locus>
```

## Practical checks
- Do not pick B1 until locus, chain map, and ownership split are explicit.
- Prefer the narrowest authoritative standards leaf, not a coarse app bucket.
- If real secrets/params/datasets are required, mark B3 unless the canon later says otherwise.
