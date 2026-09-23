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

A single-metric ranking needs a verified sort, not a composite. For a composite, use an
available non-code calculator, preserve the inputs and derivation, and disclose components,
direction, weights, and normalization. Use the user's weights when supplied. Otherwise choose explainable
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

Verify superlatives against the same eligible records used in the displayed table. Scope
“highest” to the queried population and preserve ties. A composite's top-ranked row
establishes the top score, not superiority on every input. Retain material coverage and
sample exclusions in the explanation without listing every unavailable field.

Check numeric ordering, matching periods, component coverage, and any stated bucket
thresholds. Reject zero-variance normalization and missing components rather than
producing a spurious score. If available tools cannot calculate and check a composite,
show a comparison on the underlying measures without claiming a computed ranking.

Published projections can be compared when their source, vintage, and assumptions are
compatible. Do not generate projected outcomes to fill gaps in a ranking. Follow
`output-conventions.md` for calculation and scenario limits.

Show the comparison with a table or chart that makes differences and uncertainty legible.
Keep methodological detail proportional to what the user needs to assess the conclusion.
