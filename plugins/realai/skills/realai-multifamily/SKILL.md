---
name: realai-multifamily
description: "Explore a multifamily building (5+ units) or diagnose its operations using RealAI: property overviews, finding or comparing buildings, rent and occupancy, expenses, rent upside, managers, unit pricing, and comparables. Use for 'tell me about this building' even without ownership context. Do not use for a transaction or value opinion (realai-underwriting), a geography as the subject (realai-market-research), or a standalone resident/credit profile (realai-supercensus)."
license: Proprietary
---

# RealAI Multifamily

Help the user understand a multifamily property and, when asked, improve its operations.
Ownership is not required for an overview. A bare property name or address can receive a
useful property read; do not make the user choose an analytical mode first.

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
Read `${CLAUDE_PLUGIN_ROOT}/shared/comps-guidance.md` when using rental or sales comps.

## Choose the relevant guidance

| When the question needs it | Read |
|---|---|
| Property searches, performance, expenses, rent upside, or operating risks | [asset-diagnostics.md](references/asset-diagnostics.md) |
| Property-manager performance or comparisons | [pm-assessment.md](references/pm-assessment.md) |
| Unit-level asking rents or renewals | [rent-pricing.md](references/rent-pricing.md) |
| Mapping uploaded PM reports | [report-mapping.md](references/report-mapping.md) |
| Calculating unit pricing recommendations | [pricing-calculations.md](references/pricing-calculations.md) |
| A requested pricing tracker | [action-tracker.md](references/action-tracker.md) |
| Rental comparables | [shared rental-comps](../../shared/rental-comps/SKILL.md) |
| Transaction comparables | [shared sales-comps](../../shared/sales-comps/SKILL.md) |

For a simple overview, establish the building's identity and relevant physical or operating
facts, then explain what is supported. Expand into diagnostics only when the question or
the evidence calls for it. Do not load every reference for an overview.

## Make the evidence useful

Read `${CLAUDE_PLUGIN_ROOT}/shared/interpretation-guide.md` when interpreting operating
signals. Distinguish asking from in-place rents, actual expenses from modeled benchmarks,
and market-wide weakness from property-specific performance. A gap is evidence to
investigate, not proof of management failure.

When tenant data helps explain operations, consult
`${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/topics.md` and, for cohort,
tier, or confidence interpretation,
`${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/cohort-interpretation.md`.
When the people profile itself is the requested answer, use realai-supercensus.

A market average cannot support a unit-specific rent recommendation. Use current unit
and lease records for pricing; without them, give supported property-level context and
identify what the unit decision needs. For conflicting documents, read
`${CLAUDE_PLUGIN_ROOT}/shared/document-reconciliation.md`. For rankings, composites, or
broad peer comparisons, read `${CLAUDE_PLUGIN_ROOT}/shared/multi-entity-analysis.md`.

## Calculations and presentation

Follow `${CLAUDE_PLUGIN_ROOT}/shared/output-conventions.md` for arithmetic, scenarios,
and requested files. Base derived operating comparisons on consistent source records.
Keep gross rent opportunity separate from NOI and actual results separate from assumptions.

Pricing recommendations and action trackers can be presented in a usable table. Use
available host artifact tools for requested files; do not promise model construction or
workbook validation. Variance bars, trend lines, and comp-positioning charts can make
the operating answer clearer.
