# Household questions and topics

Choose the evidence that answers the question. These twelve topic names have RealAI
SuperCensus provenance in the catalog; other demographic topics can add context under
their own source labels. Retrieval mechanics belong exclusively to
`${CLAUDE_PLUGIN_ROOT}/shared/data-retrieval/data-access.md`; coverage and source inventory belong to
`${CLAUDE_PLUGIN_ROOT}/shared/data-retrieval/topic-catalog.md` and `shared/data-retrieval/grain-coverage.md`.

| Question | Useful topics | Analytical choice |
|---|---|---|
| What is credit health here? | `credit_profile_snapshot` | Current levels and score distribution at a geography. A single FICO lookup does not require every credit metric. |
| Has credit changed? | `credit_profile_detail`, `credit_ts` | Detail contains levels and 3/6/12-month changes; use the series for a trajectory. Compare matching periods. |
| What can households afford? | `household_financials_snapshot`, `household_financials_detail` | Snapshot for a concise comparison; detail for distributions and wealth components. Match renter income to renter questions. |
| How is income changing? | `household_income_ts` | Compare all-household, renter, or owner series as the question requires. Composition can change as well as household earnings. |
| What is the education or cultural composition? | `education`, `cultural_identity` | Describe aggregate composition; do not turn it into tenant-desirability or screening criteria. |
| Which spending or lifestyle categories stand out? | `top_consumer_behaviors` | Interpret the documented index and comparison baseline. Category rank and deviation answer different questions. |
| Who is moving in and out? | `migration` | Flow totals answer volume questions; paired cohort income, wealth, and education answer composition questions. Use both when their relationship matters. |
| Who lives in this building? | `mf_tenant_profile_snapshot`, `mf_tenant_profile_detail` | Property resident evidence, with detail only when components or changes are useful. Surrounding residents are a separate population. |
| Are this building's residents changing financially? | `credit_ts`, `household_income_ts` at `property_mfr` | Comparable histories support direction; a current tenant profile alone does not. |

Read [cohort-interpretation.md](cohort-interpretation.md) when interpreting tiers,
confidence, distributions, or cohorts. Prefer a returned dollar band over an unexplained
wealth-tier number. Built-in benchmarks often answer a comparison without a separate
peer study. Snapshot/detail suffixes are hints to scope; inspect actual fields rather
than assuming that detail always adds to or excludes snapshot content.

Use aligned distributions for composition, paired bars for inbound/outbound cohorts, and
lines for comparable history. Make a visual when it clarifies the question. Credit and
income sources may have different update cycles; use returned observation dates when
available and distinguish them from source refresh metadata.
