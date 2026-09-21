---
name: realai-underwriting
description: "Evaluate real estate transactions, value ranges, refinance or buyout pricing, development and conversion feasibility, and deal documents with RealAI. Also audit, clean, or populate a real estate underwriting model. Use for a deal, valuation, or financial-model question. Do not use for a building overview or operating diagnosis (realai-multifamily), a geography as the subject (realai-market-research), or a household profile (realai-supercensus). Individual homes and 2–4 unit residential are outside this version."
license: Proprietary
---

# RealAI Underwriting

Help the user evaluate the economics and evidence behind a real estate decision. Give a
recommendation when asked for one, a value range when asked for value, or the requested
calculation or document finding. Every question does not need a verdict memo.

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

| When the question needs it | Read |
|---|---|
| Acquisition economics, development, or conversion | [acquisition-and-development.md](references/acquisition-and-development.md) |
| Value, refinancing collateral, buyout, or disposition pricing | [valuation.md](references/valuation.md) |
| Checking seller claims or reconciling a deal package | [document-verification.md](references/document-verification.md) |
| Testing material development assumptions against benchmarks | [benchmark-challenge.md](references/benchmark-challenge.md) |

Use the subject and inputs already provided. Ask only for material ambiguity or a missing
input that blocks the requested conclusion. A preliminary screen can use disclosed
assumptions and sensitivities; do not silently turn defaults into facts. Inspect the
relevant supporting records before relying on a seller's figures, without expanding a
narrow document question into a full acquisition study.

## Evidence that supports the deal

For conflicting documents, read `${CLAUDE_PLUGIN_ROOT}/shared/document-reconciliation.md`.
For interpreting market signals, read `${CLAUDE_PLUGIN_ROOT}/shared/interpretation-guide.md`.
For rent and sale comparisons, use
`${CLAUDE_PLUGIN_ROOT}/shared/rental-comps/SKILL.md` and
`${CLAUDE_PLUGIN_ROOT}/shared/sales-comps/SKILL.md` as needed.
For household evidence, use
`${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/topics.md` and
`${CLAUDE_PLUGIN_ROOT}/skills/realai-supercensus/references/cohort-interpretation.md`.
For rankings or composites, read `${CLAUDE_PLUGIN_ROOT}/shared/multi-entity-analysis.md`.

Commercial buildings have no operational property entity in this MCP. Use documents and
public web sources for building economics, with supported market-grain context. Label
those sources accurately. Individual homes, condos, and 2–4 unit valuations are outside
this version's methodology; do not apply a multifamily model to them.

## Calculation authority

- Supported multifamily NOI, direct cap, DCF, levered returns, and development yield: read and run
  `${CLAUDE_PLUGIN_ROOT}/engines/mf-operating-statement/SKILL.md`.
- Numerical forecasts: read and run `${CLAUDE_PLUGIN_ROOT}/engines/forecasting/SKILL.md`.
  Observed history and user-specified scenarios are not new statistical forecasts.
- Auditing or creating an underwriting workbook: read
  `${CLAUDE_PLUGIN_ROOT}/engines/xlsx/SKILL.md`.
- Cleaning or resetting a populated model for reuse: read
  `${CLAUDE_PLUGIN_ROOT}/engines/clean-a-template/SKILL.md`. This removes prior-deal data;
  filling a workbook uses xlsx and the supplied model structure, not the retired template filler.

Assemble calculation inputs from retrieved or supplied records, preserve units and
periods, and act on engine errors instead of fabricating results. If inputs are
insufficient, explain the affected conclusion and give the supported analysis.

For other commercial assets, represent the actual lease and cost structure in a requested
workbook under xlsx; do not force the inputs through multifamily recipes. If a calculation
path does not support the requested output, explain that specific limit.

Use charts or sensitivity tables when they clarify what drives the result. Build a
formal memo or workbook when requested; neither is an automatic consequence of asking
about a deal.
