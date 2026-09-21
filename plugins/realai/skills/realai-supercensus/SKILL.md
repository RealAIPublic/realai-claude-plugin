---
name: realai-supercensus
description: "Explore RealAI household and resident data: credit, income, wealth, education, consumer behavior, migration cohorts, and multifamily tenant profiles. Use when the people or credit picture is the answer, including 'who lives here' at a place or building. Do not use when household data is only evidence for a market conclusion (realai-market-research), operating diagnosis (realai-multifamily), or deal decision (realai-underwriting)."
license: Proprietary
---

# RealAI SuperCensus

Help the user understand aggregate household and resident patterns. Answer the requested
question: a FICO lookup does not need a full profile, and a migration comparison needs
the relevant inbound and outbound cohorts rather than every demographic topic.

## Working with the connection

Read `${CLAUDE_PLUGIN_ROOT}/shared/data-retrieval/data-access.md` before the first MCP query in the
conversation; reuse it thereafter. It owns entity resolution, schema discovery, query
construction, result handling, and recovery. Look up only the relevant sections of
`${CLAUDE_PLUGIN_ROOT}/shared/data-retrieval/topic-catalog.md` for topic selection and
`${CLAUDE_PLUGIN_ROOT}/shared/data-retrieval/grain-coverage.md` for coverage questions. Live MCP schema
wins if a stored reference disagrees.

Follow `${CLAUDE_PLUGIN_ROOT}/shared/output-conventions.md` for conversational answers,
useful visuals, sources, and material limitations. Read it once per conversation. The
user's question sets the scope; loading this skill does not commission a report.
Read `${CLAUDE_PLUGIN_ROOT}/shared/infrastructure.md` when using an imported comp,
calculation, or workbook skill; it maps the unchanged application files to this host.

## Choose the relevant guidance

- [topics.md](references/topics.md) explains which household topics answer which questions
  and when snapshot, detail, or time-series data is useful.
- [cohort-interpretation.md](references/cohort-interpretation.md) explains tiers, dollar
  bands, cohorts, percentiles, and confidence intervals. Read the relevant section before
  interpreting those fields; tier scales differ and cannot be combined as raw scores.

Other domain skills may read these references directly. They do not need to hand off a
market or property question simply because household data supports the answer.

## Make the evidence useful

Choose levels for a current-value question, distributions for composition, and comparable
observations over time for a trend. Use relevant supplied benchmarks where available;
do not assemble an unnecessary peer study. For migration, distinguish flow counts from
the income, wealth, and age composition of movers, using matching cohort definitions.

Report a wealth tier with its scale and supported dollar band, never as a dollar estimate
invented from an ordinal value. Inspect sample and confidence information internally;
qualify conclusions when uncertainty matters. Do not interpret NULL as suppression or
infer that an unreported cohort does not exist.

The catalog identifies which topics are sourced to RealAI SuperCensus. Context from
Census or other sources can help answer a household question, but retain its actual
provenance; do not relabel every demographic figure as proprietary SuperCensus data.

Describe aggregates and distributions, not facts about a named resident. Behavior indices
can support a cautious aggregate profile; they do not establish motives or preferences
of every household. Use aligned cohort charts or distributions where these clarify the
comparison, and keep units, periods, and benchmarks visible.

For rankings or composites, read `${CLAUDE_PLUGIN_ROOT}/shared/multi-entity-analysis.md`.
For wider economic interpretation, read `${CLAUDE_PLUGIN_ROOT}/shared/interpretation-guide.md`.
If the user asks for a numerical projection, read
`${CLAUDE_PLUGIN_ROOT}/engines/forecasting/SKILL.md`; run it only with a supported
history. For a requested data workbook, read
`${CLAUDE_PLUGIN_ROOT}/engines/xlsx/SKILL.md`.
