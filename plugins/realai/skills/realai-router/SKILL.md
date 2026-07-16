---
name: realai-router
description: "Route real-estate intent across the RealAI Institutional skill suite. Activate this skill at the START of any real-estate task to disambiguate scope (one entity vs. 5+, market vs. property vs. deal), purpose (capital-deployment verdict vs. asset diagnosis vs. valuation vs. discovery), and the correct downstream skill. Trigger-collision avoidance is the priority — this skill exists so the seven analysis skills below fire correctly. Activate when the user mentions any of: real estate, multifamily, MF, property, market, submarket, MSA, deal, acquisition, underwriting, valuation, pro forma, comps, tenant, operator, manager, NOI, cap rate, IRR, rent, rental, occupancy, lease, OpEx, value-add, ground-up, development, conversion, BTR, SFR, single family, homeowner, refinance, disposition, buyout, due diligence, OM, T12, rent roll, appraisal, find, screen, rank, market entry, demand drivers."
license: Proprietary
---

# RealAI Router

This skill replaces the web app's orchestration layer. It does not produce analysis itself — it determines which downstream skill should run, ensures inputs are sufficient, and hands off. **Skills-first / agents-second:** route to a single appropriate skill rather than parallel-invoking multiple, then let the chosen skill follow its own intake pattern.

## The 11 skills you route across

| Skill | Owns |
|---|---|
| `realai-data` | Data layer (entity resolution, schema discovery, query construction). Foundation called by every analysis skill. |
| `realai-investment` | Capital-deployment verdicts: Investment Screening, Acquisitions, Development Feasibility, Conversion Evaluation. Each ends in GO / NO-GO / CONDITIONAL / DEEPER-DILIGENCE-WARRANTED. |
| `realai-property-analysis` | Held-asset diagnosis: Tenant, Operating Efficiency, Mark-to-Market, PM Assessment. No buy verdict. |
| `realai-valuation` | "What is this worth" — Property Valuation, MF Sale Comps, MF Rental Comps. Serves acquisition, refi, buyout, AND disposition. |
| `realai-single-family` | Residential — SFR investor analysis (GO/NO-GO/GO-WITH-CONDITIONS) AND consumer/homeowner Home Valuation. |
| `realai-market-analysis` | Profile a NAMED market: rent dynamics, demand drivers, strategy-weighted entry scorecard. |
| `realai-discovery` | Search a POPULATION (properties or places) against criteria; return a ranked list. |
| `realai-underwriting` | Document verification (Due Diligence) AND model-driven pro forma (calls `realai-pro-forma` engine). |
| `realai-pro-forma` | Engine: writes payload into a cleaned template + manifest pair, recalculates, returns workbook. Narrow trigger — only fires when template+manifest pair is detected. |
| `realai-prepare-template` | Three-phase factory: converts a populated, macro-free Excel underwriting model into a cleaned template + manifest, then emits a personalized user-side skill. |
| `realai-brand` | Final-step formatter for deliverables. Called by every report-producing skill before returning the file. |

## Step 1 — Identify the SCOPE

How many entities of the same type does the user name?

| N | Treatment |
|---|---|
| 1 | Single-entity analysis. Hand off to the appropriate domain skill. |
| 2 | Side-by-side comparison. Same domain skill, two-column response shape. |
| 3–4 | Per-entity depth. Same domain skill, three or four mini-sections. |
| 5+ | Multi-entity discipline. The downstream skill MUST also invoke `methodology/multi-entity.md` (batched pulls, sandbox composite scoring, threshold labels, superlative verification). For `realai-discovery` this is the default; for other skills it's conditional. |

## Step 2 — Identify the PURPOSE

The user's intent maps to one of four families. Each routes differently:

| Purpose | Question shape | Route to |
|---|---|---|
| Capital-deployment verdict | "Should I buy / develop / convert this?" "Is this deal worth pursuing?" | `realai-investment` |
| Asset diagnosis (held) | "How is this property running?" "Is the manager doing a good job?" "How much rent upside is there?" "Why is OpEx so high?" "Who lives here?" | `realai-property-analysis` |
| Valuation | "What is this worth?" "Find me comps." "What's the refi value?" "What's the buyout / disposition price?" | `realai-valuation` |
| Discovery | "Find me properties / markets that..." "Rank these markets by..." "Screen for..." | `realai-discovery` |

Two additional non-analytical purposes:

| Purpose | Route to |
|---|---|
| Document verification | `realai-underwriting` (Branch B — Due Diligence) |
| Pro forma execution | `realai-underwriting` (Branch A — proforma via template) → engine `realai-pro-forma` |
| Template preparation | `realai-prepare-template` |

## Step 3 — Apply the disambiguation rules

### Rule A — Residential vs. MF/CRE is decided by DATA LAYER, not by "is it a house"

This matters because the entity type determines the data path:

| User describes | Data layer | Skill |
|---|---|---|
| Single-family home, condo, 2–4 unit residential | Zillow listing + sold + `property_residential` | `realai-single-family` |
| Multifamily (5+ units, apartments, garden, mid-rise, high-rise) | `property_mfr` semantic datamart | `realai-investment` / `realai-property-analysis` / `realai-valuation` |
| Other CRE (office, industrial, retail, hotel, self-storage, mixed-use) | `property` semantic datamart + web research | `realai-investment` / `realai-valuation` |

A 4-unit or mixed-use building can go either way. **Let the data model decide:** if it resolves through `entity_search_by_name` to a `property` or `property_mfr` entity, MF/CRE skills; if it must go through the Zillow zpid + `property_residential` pattern, single-family skill.

### Rule B — Valuation is an INPUT to investment, not a member of it

When an investment-screening or underwriting task needs a value figure, route to `realai-valuation` rather than recomputing inside investment. Keep valuation a shared input:

- Acquisitions analysis needs entry-vs-market basis → call `realai-valuation` for the basis check, fold result back into investment narrative.
- Refinance / partner buyout / disposition pricing → these are valuation purposes, NOT investment purposes. Route directly to `realai-valuation`.
- Investment screening's one-page snapshot includes a "last sale + implied cap rate" line, not a full valuation. If the user asks for a value range, escalate to `realai-valuation`.

### Rule C — Open-ended / generalist questions

When the user asks "tell me about this property" or "what's the story on this market" with no stated purpose:

- **Claude is the generalist.** Use the `realai-data` skill directly to pull what's needed and respond conversationally.
- Do NOT invoke an analysis skill as a fallback — analysis skills carry verdict-shaped response structures that don't fit open-ended asks.
- If the user's follow-up reveals a specific purpose (verdict, diagnosis, valuation, discovery), hand off then.

This replaces the dropped Property Generalist and Area Generalist agents.

## Step 4 — Skill-vs-skill collision avoidance

These collisions are the ones to watch for. When intent is genuinely ambiguous, ask the user one targeted question before invoking.

| User says | Could route to | Disambiguate by |
|---|---|---|
| "Underwrite this deal" / "screen this acquisition" / "run the numbers on" | `realai-investment` (default) | The investment skill internally invokes `realai-pro-forma` to populate the workbook and reads outputs back, then wraps them in an analytical writeup. Returns BOTH the populated `.xlsx` AND the verdict + thesis + comps + risks. Use `realai-underwriting` ONLY when the user explicitly asks for document verification or raw engine output (see next two rows). |
| "Verify the OM" / "due diligence on" / "do the numbers tie" / "reconcile the T12" | `realai-underwriting` Branch B (Due Diligence) | Documents-driven verification only. Produces Clear / Conditional / Material Concerns. Does not run a pro forma. |
| "Just populate the template" / "run the manifest with these numbers" / "give me the workbook only, no writeup" | `realai-underwriting` Branch A → `realai-pro-forma` engine | Explicit engine-only request. Returns the populated workbook + short receipt, no analytical narrative. Reserve this for power users who specifically don't want the writeup. |
| "What's this property worth?" / "refi value" / "buyout price" / "disposition pricing" | `realai-valuation` (always) | Never investment — valuation is the right home regardless of downstream purpose. |
| "Find me X" / "rank Y" / "screen for Z" | `realai-discovery` | Always discovery when the user is searching a population. |
| "Should I renovate?" | `realai-property-analysis` (Mark-to-Market) or `realai-investment` (value-add Acquisitions) | If user owns the asset → property-analysis. If user is acquiring with renovation as the thesis → investment. |
| "Is this a good market?" | `realai-market-analysis` or `realai-discovery` | If they named ONE market → market-analysis. If they're asking which market(s) to pick → discovery. |
| "Help me with my Excel model" / "clean my underwriting model" / "make this reusable" | `realai-prepare-template` | Cleaning + manifest-building a populated model. Emits a personalized `.plugin` zip for re-installation. |

### The key rule for "underwrite" intent

When the user wants to underwrite a deal, they almost always want BOTH a populated workbook AND an analytical writeup wrapping those numbers. `realai-investment` is built to deliver both — it dispatches to `realai-pro-forma` internally for the workbook math, then wraps the outputs in the analytical narrative. Default to `realai-investment`.

`realai-underwriting` is reserved for two narrow cases:
1. **Document verification** — the user has documents and wants them pressure-tested, but is not asking for a pro forma run.
2. **Explicit engine-only output** — the user specifically asks for raw workbook outputs without a writeup. This is rare; reserve for power users who know they want it.

## Step 5 — Hand off

Once you've identified the right skill, your job is done — invoke it and step back. The chosen skill carries its own intake form, sufficiency checks, research patterns, calculation routes, and response shape. Do not narrate the routing decision to the user; just let the chosen skill take over.

## Output discipline (applies to every downstream skill)

Every skill in this plugin inherits the following rule:

**Interim reasoning stays in the thinking block.** Branch resolution, sufficiency logic, source-class bookkeeping, calculation choreography, internal synthesis, methodology selection — minimize appearance in chat. What the user sees, in order, is:

1. **Intake forms** — `ask_user` blocks defined by the skill.
2. **confirmation only when load-bearing** — i.e., the resolved branch / mode / asset class materially shapes the next form the user is about to see. One line, no preamble, no commentary. Skip entirely when the next step is the deliverable itself.
3. **Genuine blocking clarifications** — only when the analysis would be wrong without an answer. Not for confirming choices the skill can reasonably default.
4. **The final deliverable**, opened with the response-header convention below.

What does NOT appear in chat: narrating the routing decision, listing what the skill is about to do, restating the user's question, previewing methodology, "state mode + asset class" lines that echo what the user just said, summaries of which sub-skill is being dispatched, step-by-step accounts of which data was pulled, or "now I'll..." transitions. Skills' `### Internal synthesis (work through; do not output verbatim)` blocks are internal by design — work through the questions in thinking, do not surface them.

This rule degrades over a long agentic run: by the time a skill is several tool calls deep into retrieval and math, this section is far back in context and the model drifts into progress narration. To counter that, **each downstream skill restates a short "Execute silently" reminder at its own Research and Calculations sections** — proximate to where the urge to narrate actually strikes. Those inline reminders are not redundant; they are the load-bearing copy. Honor them where they appear, not merely here.

**Data-recency convention (applies to every downstream skill)**

When a date appears in the data — a last-sale date, a T12 period end, a permit-issue
date, a lease expiration, an assessment year — compute the elapsed time and describe
it relative to today, rather than quoting the raw date or a vague adverb. "Sold 14
months ago," not "sold in 2025" and not "sold recently." "T12 ends 4 months stale,"
not "recent financials." The reader is making a time-sensitive capital decision; how
old a figure is changes how much weight it carries, and a bare date forces them to do
the subtraction the analysis should have done. Round to the natural unit (days, weeks,
months, years) and name the reference point when it isn't obviously today.

### Response-header convention

Every domain skill's deliverable opens with a horizontal rule and a bold deliverable header on its own line, naming the specific analysis and subject:

```
---

**[Analysis name] — [Subject identifier]**
```

Examples: `**Acquisitions Analysis — 1234 Main St, Charlotte NC**`, `**Valuation Memo — Park Place Apartments**`, `**Market Entry Scorecard — Charlotte MSA (value-add MF)**`, `**Due Diligence — Park Place OM package**`. Each domain skill's Response section names the appropriate header text for that branch or frame.

The horizontal rule + bold header is the unambiguous "analysis complete, response begins" signal. Nothing in chat between the last intake form (or single confirmation line) and this header.

## What this skill does NOT do

- Produce analysis
- Pull data
- Run pro forma math
- Format deliverables (that's `realai-brand`)
- Replace `realai-data` — every consuming skill still goes through `realai-data` for entity resolution and queries
