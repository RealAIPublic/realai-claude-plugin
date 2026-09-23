---
name: realai-market-research
description: "Explore and compare real estate markets, neighborhoods, ZIP codes, and other geographies using RealAI: rents, housing supply, demand, market selection, commercial sectors, rates, and capital markets. Use for questions about a place or finding places that fit a strategy. Do not use for a building overview or operations (realai-multifamily), a transaction or value opinion (realai-underwriting), or a household/credit profile as the answer (realai-supercensus)."
license: Proprietary
---

# RealAI Market Research

Help the user understand a place, compare places, or find markets that fit their needs.
Start with what they want to know. A bare place name can receive a useful geographic
overview; a question about rent needs rent evidence, not a full market-entry study.

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

## Choose the relevant guidance

| When the question needs it | Read |
|---|---|
| An open-ended geographic overview | [open-ended-reads.md](references/open-ended-reads.md) |
| Rental conditions, supply, demand, or investment fit | [market-read.md](references/market-read.md) |
| How evidence matters to a particular strategy | [strategy-calibration.md](references/strategy-calibration.md) |
| Finding or ranking markets against criteria | [ranking.md](references/ranking.md) |
| Help turning an investment thesis into criteria | [example-theses.md](references/example-theses.md) |
| Rates, financing context, or commercial cap rates | [macro-and-capital-markets.md](references/macro-and-capital-markets.md) |

Comparison and ranking follow the user's intent, not a fixed count of places. Do not
invent a weighted score when the user wants a side-by-side comparison. For rankings,
composites, or broad peer sets, read `${CLAUDE_PLUGIN_ROOT}/shared/multi-entity-analysis.md`.

## Make the evidence useful

Use `${CLAUDE_PLUGIN_ROOT}/shared/interpretation-guide.md` when interpreting operational
or market relationships. For household or migration evidence, read
`${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/topics.md`; when interpreting
tiers, cohorts, or confidence fields, read that skill's
`${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/cohort-interpretation.md`.
This evidence can support a market answer without switching skills.

Keep the user's geography identifiable. A parent-market benchmark is context, not a
measurement of the requested neighborhood. Distinguish permits from delivered or
under-construction supply. Compare sources at compatible dates; a catalog refresh date
does not make every observation current.

Commercial-sector context exists at market grain, not for individual commercial buildings.
Geographic home-value and SFR-rent questions belong here; individual home valuations are
outside this version's coverage. A multifamily building overview belongs to realai-multifamily.

## Calculations and presentation

Follow `${CLAUDE_PLUGIN_ROOT}/shared/output-conventions.md` for derived measures and
requested artifacts. Use observed history for trends. A published projection retrieved
from the MCP retains its source and vintage; a user-specified growth path is a scenario
assumption. Do not generate a new statistical forecast or confidence band in this edition.

Show trends, comparisons, and tradeoffs visually when helpful using the host's available
non-code tools. A chart or comparison table does not require an Excel deliverable.
