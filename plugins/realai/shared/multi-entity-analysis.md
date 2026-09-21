# Comparing and ranking entities

Use for ranked searches, composite scores, or broad peer comparisons. The user's question
determines whether to rank, compare, or profile; five entities do not automatically require
a scorecard. These rules preserve comparability and reproducibility, not an output format.

## Define the population and comparison

For named subjects, resolve their identities. For a criteria-defined search, obtain the
candidate pool from a query rather than recalled examples. Make geographic boundaries,
filters, and exclusions explicit when they affect who can win. Page or batch according to
`data-retrieval/data-access.md`; a limited page is not a complete national ranking.

Use the same metric definitions and compatible periods across the set. Prefer supplied
benchmarks when they match the question. A national z-score and a z-score computed within
five selected markets use different populations; do not mix them as interchangeable.
Distinguish realized growth from a forward projection.

## Compute only the score the question needs

A single-metric ranking needs a verified sort, not a composite. For a composite, calculate
in code, preserve the inputs and derivation, and disclose components, direction, weights,
and normalization. Use the user's weights when supplied. Otherwise choose explainable
weights or equal weights; identify the choice and test sensitivity if close ranks depend
on it. A qualitative axis requires a labeled proxy or a separate qualitative comparison.

Do not add raw tiers from different wealth families. Do not compare text-encoded numbers
lexicographically. Coerce numeric values while preserving NULL and explicit zeros.

Use one consistent eligible record set for a scoring pass. Do not silently fill missing
components with zero, reweight individual rows, or patch a few scores in a second pass.
Either compare a supported subset or revise the common components with an explicit
coverage note. Imputation requires a justified, disclosed method and is not the default.

Apply any quantitative bucket thresholds uniformly. Investigate all-one-bucket results;
do not move thresholds merely to manufacture differentiation. Qualitative synthesis is
allowed, but do not imply it is a computed rating.

## Verify the claims

Use the bundled standard-library checker on records assembled programmatically from the
retrieved data. It fetches nothing and does not know the appropriate domain assumptions.

| Check | Purpose | Arguments after `--check` |
|---|---|---|
| `coverage` | Detect unavailable components | `coverage records.json` |
| `reliability` | Apply a justified sample-size floor | `reliability --field households_sample_size --min 2000 records.json` |
| `extremum` | Verify highest/lowest, including ties | `extremum --field rent_growth --direction max --claim Raleigh records.json` |
| `predicate` | Verify claims such as “only positive” | `predicate --field rent_growth --op gt --value 0 --claim Raleigh records.json` |
| `buckets` | Inspect categorical distribution | `buckets --field label --expected Strong,Mixed,Weak records.json` |
| `composite` | Weighted z-score sum, normalized to mean 50 / SD 10 | `composite --components a,b --weights 0.6,-0.4 records.json` |

Run with the actual plugin path substituted by the host:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/shared/scripts/cross_check.py" --check coverage records.json
```

The table uses illustrative field names and sample floor; select justified values for the
actual analysis. Input is an array of records or an object containing `records`; the entity
label defaults to `entity` (`--entity` overrides). Negative composite weight means
lower-is-better. The composite refuses NULL and zero-variance components. Inspect error
status rather than assuming the command succeeded.

Verify superlatives against the same eligible records used in the displayed table. Scope
“highest” to the queried population and preserve ties. The composite's top-ranked row
establishes the top score, not superiority on every input. Retain material coverage and
sample exclusions in the explanation without listing every unavailable field.

For actual forecasts, use `${CLAUDE_PLUGIN_ROOT}/engines/forecasting/SKILL.md` and
supported histories before ranking projected outcomes. If the runtime cannot execute a
required scoring or verification step, do not present the result as a validated ranking.

Show the comparison with a table or chart that makes differences and uncertainty legible.
Keep methodological detail proportional to what the user needs to assess the conclusion.
