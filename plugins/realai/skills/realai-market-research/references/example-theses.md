# Turning a thesis into evidence

These examples show how to translate a question into criteria. They are not a menu,
mandatory query bundles, or predefined scoring models. Confirm the actual fields and
definitions through the shared catalog and live schema. A strategy can justify a
qualitative comparison without a composite or numerical forecast.

| Thesis | Candidate evidence | Interpretation to preserve |
|---|---|---|
| Rental investment fundamentals | Achieved tradeouts, occupancy, days on market, job growth, rent-to-income, competing supply | High asking growth alone does not establish collectible rent growth; cash flow also requires price and expenses |
| Cap-rate opportunity | Covered market/asset-class cap-rate history, Treasury context, demand and supply | Cap-rate expansion may reflect deterioration; a high cap rate is not automatically underpricing. Historical band analysis uses the capital-markets engine |
| Supply-constrained rent growth | Achieved rent growth, population or household growth, occupancy, permits relative to matching stock | Read demand and supply together; permits measure intentions and must not be described as deliveries |
| Migration-supported demand | Net migration relative to size, inbound/outbound income and wealth differences, employment, affordability | Both volume and cohort composition matter; neither alone proves future rent growth |
| Affordable places | Rent-to-income and value-to-income measures, income distribution, poverty and housing context | Lower ratios usually imply greater affordability; population or sample count is an eligibility consideration, not a reward for size |
| Recovering distressed markets | Weak trailing values, evidence of an employment or leasing turn, moderate competing supply, entry basis | A low value or weak trailing return is not enough; require evidence for the recovery hypothesis |
| Where younger households are arriving | Inbound age and inbound flow relative to the local population, with relevant peer context | Use inbound age, not age of departing residents. Flow destination IDs identify places and cannot be ranking scores |

Examples of field hints include `tradeout_new_lease_pct_avg`, `occupancy_latest`,
`days_on_market_leases_signed_past_30d`, `job_growth_1_year`, and documented
rent-to-income, value-to-income, and migration percentile variants. Prefer the current
schema's definition over the name's apparent meaning.

Some useful signals are directly available in snapshots; others need a derived ratio
or comparable history. For example, permit acceleration compares T12 with prior T12,
and cap-rate direction needs the observed quarterly series rather than an invented
precomputed-change field. At market grain, populated supply snapshots may already carry
the permit counts needed for the question.

Translate a broad criterion into a defined measure before weighting it. “Low supply”
could mean low under-construction stock share, low permit intensity, or slowing permit
issuance; those answer different questions. If only a proxy is available, explain why it
is useful and what it does not establish. A parent-market observation is context for
finer areas, not an area-specific score that differentiates identical parent values.

For a composite, use the declared directions, comparable scales, common eligibility,
and reproducible calculations in ranking.md and the shared multi-entity guidance.
Use a numerical forecast only if projected outcomes are actually part of the question.
