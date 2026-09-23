# Using shared comparables

Underwriting and Multifamily use the same rental and sales comp methods. Read only the
method needed for the question.

| Question | Read |
|---|---|
| Rental positioning and comparable rents | `${CLAUDE_PLUGIN_ROOT}/shared/rental-comps/SKILL.md` |
| Comparable transactions and price evidence | `${CLAUDE_PLUGIN_ROOT}/shared/sales-comps/SKILL.md` |

Use the authenticated MCP through `data-retrieval/data-access.md`. Current tool schemas
control query construction. Keep the source methods' selection criteria, eligibility
checks, and retrieval scopes. Do not copy those rules into a domain reference.

The caller's question sets the output scope under `output-conventions.md`. Return the
relevant evidence and selection rationale without turning every comp search into a
valuation or recommendation report.

Use supported coordinates and an available non-code calculation tool for distance. If
distance cannot be calculated, do not claim the results are the nearest comps or assign
invented distances. Explain the consequential selection limit and present the supported
comparison. A bounded sales pool is not an exhaustive geography-wide ranking.

Keep rent definitions, sale dates, concessions, unit mix, and comparability visible when
they affect the conclusion. Only make completeness or proximity claims the retrieval
and calculations support. A field-specific source definition of NULL does not establish
that all unavailable values mean zero, suppression, or absence.
