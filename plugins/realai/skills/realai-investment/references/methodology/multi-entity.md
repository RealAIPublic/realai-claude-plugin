# Multi-Entity Analysis Methodology

> **Module type:** Process spine. Plain markdown reference file — NOT a triggerable skill. Referenced by `realai-discovery` (always — discovery is inherently multi-entity) and by `realai-market-analysis`, `realai-property-analysis`, `realai-investment` when the consuming skill detects 5+ entities of the same type.

## Purpose

Enforce methodological discipline when comparing five or more entities of the same type — geographies, properties, deals, borrowers, tenants, or any peer set. This methodology does not govern output shape or domain interpretation; those belong to the domain skill. Its job is to ensure that any cross-sectional claim, score, label, or ranking produced by the analysis can be **verified and reproduced**.

## When to invoke

Activate when any of the following are true:

- The user names five or more entities of the same type
- The request uses language like "rank by," "compare these," "top N," "screen for," "across all"
- The output will position entities against each other rather than analyze each in isolation
- A composite score, ranking, or categorical bucket will be produced

Do NOT activate for:

- One entity analyzed with peers as background reference
- Two-entity comparisons (use side-by-side framing)
- N ≤ 4 where per-entity depth is the goal

## Rule 1 — Batch the pulls

Pull data for all entities in as few calls as possible. Use filter-by-list or array ID parameters wherever the data catalog supports them. Never iterate one call per entity.

If you find yourself writing a loop with one query per entity, stop — there is almost always a batched form. Resolve this before proceeding.

## Rule 2 — Compute composites in code, not in prose

If the analysis produces a composite score, write the scoring function in the Python sandbox, run it on the assembled data frame, and preserve the script.

Never assert a composite value without code that produced it. Z-scoring and normalization done mentally will be wrong often enough to invalidate the output, and a published score with no derivation path cannot be reproduced.

**Minimum pattern:**

```python
import pandas as pd

def composite_score(df, components):
    z = (df[components] - df[components].mean()) / df[components].std()
    raw = z.sum(axis=1)
    # Normalize to mean=50, std=10
    return 50 + (raw - raw.mean()) / raw.std() * 10

df['score'] = composite_score(df, ['metric_a', 'metric_b', 'metric_c'])
```

Save the scoring script and record its file ID. This ID becomes an input to the methodology record if the analysis is recurring.

## Rule 3 — Apply categorical labels via thresholds, not judgment

Any bucket label — "Strong / Mixed / Weakening," "Buy / Hold / Avoid," "Tier 1 / 2 / 3," "High / Mid / Low" — must be produced by a thresholded function applied to a numeric input. Do not assign labels entity-by-entity in prose.

**Minimum pattern:**

```python
def demand_label(row):
    if row['gdp_growth'] >= 5.0 and row['net_migration'] >= 0:
        return 'Strong'
    elif row['gdp_growth'] <= 2.5 or row['net_migration'] < -0.5:
        return 'Weakening'
    else:
        return 'Mixed'

df['label'] = df.apply(demand_label, axis=1)
```

**Before publishing, sanity-check the distribution:**

- If one bucket is empty, the thresholds are miscalibrated
- If all entities land in the same bucket, the categorical is not earning its keep — either tighten the thresholds or drop the label

Document the thresholds. They become part of the methodology record.

## Rule 4 — Verify superlatives before claiming them

Any claim of the form "only X," "highest Y," "lowest Z," "fastest W," "most A" across the dataset must be verified programmatically against the assembled data frame before it is written.

This is the highest-frequency factual error in cross-sectional work. A model will scan a table, write "the only market with positive FICO trend," and miss two other rows that are also positive.

**Minimum pattern:**

```python
# Before writing "Charleston is the only market with positive FICO trend":
qualifying = df[df['fico_t12_pct_chg'] > 0]
print(qualifying[['entity', 'fico_t12_pct_chg']])
# len(qualifying) == 1 → claim is safe
# len(qualifying) > 1 → rewrite: "one of N markets with..."
```

If a superlative survives this check, write it. If it does not, weaken the claim or drop it. Never carry an unverified superlative into the output.

## Rule 5 — Flag inconsistent time horizons inside composites

If a composite mixes metrics with different time horizons — T6 for one input, T12 for another, ACS vintage for a third — flag it before computing.

Mixing horizons without disclosure produces a number whose meaning drifts as inputs update at different frequencies. Either align the horizons or document the mismatch explicitly and justify it. This flag passes to the methodology record if the analysis is recurring.

## Handoff back to the domain skill

This methodology is the process spine. It does NOT:

- Decide what to pull or how to interpret metrics (the domain skill's job)
- Determine output shape or narrative structure (the domain skill's job)

After applying these five rules to assemble the data frame and verify claims, the domain skill takes the verified frame and produces its native response shape (table-plus-standouts for markets, ranked comparison for properties, etc.).
