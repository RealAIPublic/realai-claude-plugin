# A requested unit-action tracker

Use this reference when the user asks for a pricing tracker, workbook, or reusable unit
worklist. Recommendations can otherwise stay in chat. Adapt the workbook to the user's
existing process or supplied template instead of imposing a fixed report format.

Before creating the artifact, read `${CLAUDE_PLUGIN_ROOT}/shared/infrastructure.md` for
host invocation, then use `${CLAUDE_PLUGIN_ROOT}/engines/xlsx/SKILL.md` for workbook
construction and validation. Use the same calculated records for the workbook, any chart,
and the explanation so their units, dates, rents, and totals agree.

## Make the worklist usable

A compact action table generally needs unit, status, proposed action, proposed rent,
action or review date, and a short reason. Include current rent, comparable target or
range, floorplan, lease end, concession assumptions, and source dates where they support
review. A summary of urgent actions is useful for a long list, but it need not repeat
every row or force a predetermined number of priorities.

Suggested action labels include list, review ask, send renewal, pre-market, hold, verify
status, and review payment exception. Adapt labels to the user's workflow. Keep assumptions
and pending checks distinct from executable instructions. A payment exception alone does
not justify a nonrenewal instruction.

An action note should explain the evidence, proposed step, and any condition needed for
execution. For example: “Current ask is $1,750 versus comparable net-effective rents of
$1,650–$1,700. Review a $1,700 target after confirming the advertised concessions apply.”
Do not promise a leasing outcome or claim that a building-level income measure describes
this resident. When a confirmed legal cap changes the recommendation, show both the
supported target and applicable capped result on a consistent rent basis.

## Fields, dates, and totals

Use actual dates for known lease ends and supported action timing. Label estimates and
conditional dates; do not manufacture exact dates from aggregate expiration counts.
Keep listing duration and physical vacancy in separate columns when both are relevant.
A missing listing field is unknown, not an affirmative unlisted status.

Preserve all units within the requested scope, including unmatched units. Retain down,
model, and administrative units where useful, with their revenue treatment explicit.
No missing rent or status should silently become zero. Distinguish formula blanks,
unknown values, and zero where calculations depend on the difference.

Summaries need consistent populations and rent bases: total units, occupancy, weighted
rents, current market gaps, and conditional capture estimates are different measures.
Do not add an above-market retention action to positive upside or equate a price reduction
with incremental rent. A ranking may use urgency, vacancy exposure, or credible opportunity;
state which, and keep unlike measures separate.

## Presentation and verification

Keep primary actions visible and supporting detail easy to inspect. Freeze headers,
use readable currency/date formats, wrap notes, and avoid clipping. Optional column
outlines can group secondary detail, but essential instructions must remain visible.
If a format relies on a feature the user's viewer may not expose, ensure the information
is still accessible without it.

A ranked action chart, rent-position comparison, or monthly expiration chart can help
when it reveals a decision. Build chart records from the same unit table and identify
cohorts honestly. A cohort count cannot be represented by an invented unit. Label scenario
or estimated data rather than imply observed precision; skip charts that add no insight.

Validate identifier uniqueness, row populations, formulas, dates, totals, filters, and
any collapsed-detail behavior before delivery. Do not embed unnecessary resident names,
contact details, or payment information in a shareable operating worklist.

## Updating a prior tracker

When asked to update a supplied or session-created tracker, compare on stable unit
identifiers and matched rent/period definitions. Useful changes include newly leased
units, revised pricing evidence, upcoming expirations, and verified actions completed.
A changed observation does not prove an operator followed or ignored a recommendation;
use execution evidence before claiming either. Preserve the prior version or identify
the revision clearly, and explain material changes without restating the whole workbook.
