# RealAI

Explore real estate data, evaluate opportunities, and work through property questions
with your RealAI connection in Claude Code and Cowork.

## Four skills

| Skill | What it helps you do |
|---|---|
| **Multifamily** | Understand a building, find and compare properties, diagnose operating performance, and evaluate rents, expenses, and unit pricing. |
| **Market Research** | Explore a geography, compare markets, identify promising locations, and understand rent trends, housing supply, demand, and capital markets. |
| **SuperCensus** | Understand residents and households through income, credit, wealth, consumer behavior, and migration data. |
| **Underwriting** | Evaluate a transaction, estimate value, test acquisition or development assumptions, reconcile deal documents, and work with underwriting models. |

Ask a quick question or explore a decision in depth. Follow-up questions build on the
conversation. Charts, comparisons, and interactive visuals help explain the evidence
where supported. Request a memo, workbook, or pricing tracker when you need a deliverable.

## Structure

The four skills draw on shared guidance and specialized tools as the question requires.

| Component | Used for |
|---|---|
| `skills/` | Choosing the relevant real-estate approach and interpreting the results. Each skill includes focused guidance for its subject. |
| `shared/` | Interpreting evidence consistently, reconciling documents, comparing entities, and presenting clear answers and useful visuals. |
| `shared/data-retrieval/` | Finding the right RealAI data and querying it through the MCP connection. Contains the retrieval workflow, topic catalog, and coverage guide used by all four skills. |
| `shared/rental-comps/` | Selecting and comparing rental properties to assess competitive rents and positioning. Used by Multifamily and Underwriting. |
| `shared/sales-comps/` | Selecting and comparing property sales to inform transaction analysis and valuation. Used by Multifamily and Underwriting. |
| `engines/forecasting/` | Calculating forecasts, scenario ranges, and capital-market historical bands. |
| `engines/mf-operating-statement/` | Calculating multifamily operating statements, NOI, valuations, and investment returns. |
| `engines/clean-a-template/` | Removing prior-deal information from a populated workbook while preserving reusable model logic. |
| `engines/xlsx/` | Reading, auditing, building, editing, and populating Excel workbooks, with formula and integrity checks. |

For example, a rent-upside question can use Multifamily with shared rental comps. An
acquisition analysis can combine Underwriting with comps and operating calculations.
Preparing a model for another deal uses clean-a-template; populating it uses xlsx.
