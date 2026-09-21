# Model Integrity Review

The deep reference for the single most important rule in this skill: a workbook
with zero Excel errors can still be wrong. Read this whenever you build, edit,
or audit a financial model. SKILL.md links here from "Error-Free Is Not Correct".

## Contents

- The core failure mode
- Failure catalog (error-free but wrong)
- The integrity scan (workbook_integrity_scan.py)
- Structural integrity review checklist
- Dynamic scenarios and sensitivities
- Schedules must reconcile to their timing
- Formats, labels, and units
- Severity ordering

## The core failure mode

Excel reports an error only when a formula cannot evaluate. It says nothing
when a formula evaluates cleanly to the wrong number. That silent class of
defect is what loses customer trust, because the workbook looks finished and
audits clean on a casual glance. Every other rule in this section exists to
catch it. Treat structural correctness as the primary deliverable and visual
polish as secondary.

A clean recalc (zero #REF!, #DIV/0!, #VALUE!, #N/A, #NAME?) is necessary but
not sufficient. After recalc passes, you have only proven the formulas run, not
that they compute the right thing.

## Failure catalog (error-free but wrong)

Each of these computes without an Excel error and is wrong anyway:

1. Formula points at the wrong cell. A total that sums `B2:B9` when the data
   runs `B2:B12`, or a reference off by one row. The number looks plausible.
   Verify the range covers exactly the intended cells, top and bottom.

2. Reference resolves through an empty header row. A lookup or a structured
   reference keyed off a header silently returns the wrong column when a header
   cell is blank. Confirm every header cell a formula depends on is populated.

3. Metric identity confusion. The label names one metric and the formula
   computes another. The dangerous swaps are near-synonyms: gross vs effective,
   leased vs physical occupancy, margin vs ratio, value-over-cost vs
   value-over-rate, cap rate vs yield-on-cost, asking vs in-place rent. The
   related variant is the same metric computed two different ways on two sheets.
   Read the adjacent label and confirm the formula computes that exact concept,
   not a plausible neighbor, and reconcile any metric that appears twice.

4. Static paste over a formula. A projection period that was pasted as a value
   no longer recalculates. The row reads as a clean series, but one cell is
   frozen. See the integrity scan below.

4a. Dead model: the whole sheet is pasted values. The worst form of the above is
   a pro forma, schedule, or sensitivity built by computing every result in
   Python (or by hand) and writing the numbers as literals, with no formulas at
   all. It looks complete and the numbers may even be right today, but nothing
   recalculates and the cells often carry absurd precision (NOI as
   1032834.5539344). The `hardcoded_outputs` scan flags a computed sheet with
   almost no formulas. Build outputs as formulas that reference the inputs;
   never paste Python-computed results.

5. Assumption baked into a formula. `=B5*1.03` hides the growth rate inside the
   math, so a reviewer cannot find or change it and a sensitivity cannot reach
   it. Move the 1.03 to a labeled input cell and reference it with a locked
   address.

6. Unit or scale mismatch. Multiplying a monthly figure by an annual rate, or
   mixing per-unit and aggregate values in one calculation. The arithmetic is
   valid; the meaning is not.

7. Sign convention drift. Expenses entered positive in one section and negative
   in another, so a subtotal double-counts the sign. Check that every component
   of a subtotal carries the convention the subtotal expects.

8. Disconnected or orphaned logic. A schedule that computes but feeds nothing, an
   assumption defined but never referenced, or a surface whose numbers contradict
   an assumption used elsewhere. These are missing connections, not wrong values,
   so they pass every arithmetic check. Trace each input to a consumer and each
   schedule to a destination; the scan's `orphaned_name` finding catches the
   defined-name case.

9. Double-counting across rows. Each row looks correct alone while a subtotal
   counts the same dollars or units twice: a cost in both a line item and an
   allocated total, a unit in two cohorts, a cumulative count that runs past its
   physical limit. Confirm the components of every subtotal are mutually
   exclusive, and bound cumulative series at their cap (total units, 100 percent).

## The integrity scan (workbook_integrity_scan.py)

Run this read-only scan early when auditing, and again after building or editing
before you recalc and deliver:

```bash
python skills/xlsx/scripts/workbook_integrity_scan.py <file.xlsx> --json output/integrity.json
```

It surfaces the silent defects recalc cannot see. Structural categories:

- `numbers_as_text`: a calculated quantity stored as a presentation string
  ("$24.0M", "12.5%", "(1,234)") instead of a numeric cell with a number format.
- `hardcoded_outputs`: a computed-surface sheet (pro forma, schedule, sensitivity,
  scenario) with almost no formulas, so its numbers are pasted and the model is dead.
- `no_formulas`: a workbook with substantial numbers across two or more sheets but
  zero formulas anywhere; every computed value is pasted. Name-agnostic, so it
  catches a comps or summary workbook whose sheet names are not computed surfaces.
- `derived_hardcode`: a hardcoded number under a derived analysis header (Adjusted
  Rent, Implied Premium/Discount, Total Adj, Margin, Yield), a dead analysis cell.
- `blank_reference`: a formula referencing an empty cell (e.g. `=-D6*C22` with C22
  blank), so the term silently evaluates to 0. Catches a wrong reference buried in
  arithmetic that the pure-link check cannot see.
- `static_paste`: a hardcoded number sitting between two formula cells along a
  row or column, the classic pasted-over period.
- `blank_table_header`: an Excel table whose header row has an empty cell.
- `label_link_mismatch`: a link cell (`=OtherSheet!X`) whose row label names a
  different metric than the cell it points at, or that resolves to a blank cell.
  This catches the off-by-one summary cascade and the wrong-but-plausible
  cross-sheet reference.
- `stored_formula_error`: a cached Excel error already in the file.
- `formula_literal` (advisory): a numeric literal embedded in a formula that may
  be an assumption that belongs in an input cell.
- `orphaned_name` (advisory): a defined name no formula references.

Presentation categories:

- `stray_symbol`: a decorative glyph, icon, arrow, bullet, or em/en dash in a
  cell (HIGH); a math-operator symbol used as text (advisory).
- `merged_cells` (advisory): a merge that fragments the grid (multi-row, or
  multi-column inside the body).
- `color_role` (advisory): a formula cell with blue font, the color reserved for
  inputs.
- `narrow_column` (advisory): unwrapped text wider than its column whose neighbor
  is occupied, so it is cut off. Width is allowed to vary; only real clipping flags.
- `freeze_panes` (advisory): a freeze pane on a sheet that fits on screen, or
  freeze positions inconsistent across the workbook.
- `font_consistency` (advisory): body text mixing font sizes or families on a sheet.
- `embedded_newline` (advisory): a hard line break typed inside a cell instead of
  wrap-text alignment.
- `number_format` (advisory): a column mixing formatted numbers with unformatted
  (General) cells.
- `alignment` (advisory): numbers not right-aligned, or mixed vertical alignment.
- `total_row_style` (advisory): a total/subtotal row (any sum/add/subtract
  formula, not just SUM) that is not bold.
- `clipped_row` (advisory): a fixed row height too short to show its wrapped text,
  so content is clipped. Height is allowed to vary; only real clipping flags.
- `number_too_wide` (advisory): a formatted number wider than its column, so the
  cell shows #### instead of the value.
- `unlocked_anchor` (advisory): a single anchor cell referenced by a run of sibling
  formulas with a relative address; a fill would drift off it. Lock it with $.
- `header_style` (advisory): header bars using more than one fill color.

The script exits non-zero when any HIGH-severity finding exists, so it chains in
a feedback loop:

```bash
python skills/xlsx/scripts/workbook_integrity_scan.py output.xlsx && \
python skills/xlsx/scripts/recalc.py output.xlsx
```

Treat HIGH findings as defects to fix before delivery. Treat `formula_literal`
as a review prompt: some literals are legitimate (counts, unit conversions),
but rates, margins, and multiples must move to input cells. The scan is a net,
not a substitute for reading the model. It cannot detect a wrong-cell reference
or a similarly named metric; the review checklist below covers those.

## Structural integrity review checklist

Copy this and check off each item before delivering or concluding:

```
Integrity Review:
- [ ] Recalc passes with zero formula errors
- [ ] Integrity scan run; all HIGH findings resolved or justified
- [ ] Every total's range covers exactly the intended rows and columns
- [ ] 2-3 sample references spot-checked against the cells they should hit
- [ ] Every cross-sheet link's label matches the label of the cell it points at (no off-by-one cascade)
- [ ] Headline outputs (NOI, EGI, value, yield) independently recomputed and tie to the displayed cells
- [ ] Each label's formula computes that exact metric, not a near-synonym
- [ ] Any metric appearing on two sheets is computed the same way and ties; stated benchmarks match the cells
- [ ] No assumption baked as a literal inside a formula
- [ ] No formula multiplies or divides by a blank cell (a rate pulled from the wrong row reads as zero)
- [ ] Shared anchors locked with $ so fills do not drift off them
- [ ] Scenario and sensitivity interior cells reference row/column drivers
- [ ] Time-based schedules show every intervening period, no jumps
- [ ] Cumulative series capped at their physical limit; no subtotal double-counts
- [ ] Every input feeds a consumer; every schedule feeds a destination
- [ ] Every derived value is a formula (averages, adjustment grids, per-SF, ratios), not a pasted number; raw imported data may be hardcoded but the analysis on it may not
- [ ] Units and scale consistent across every multi-term calculation
- [ ] Sign conventions consistent within every subtotal

Presentation Review:
- [ ] No stray symbols, emoji, or em/en dashes in cells
- [ ] Numbers stored as numbers, not text
- [ ] Number formats match convention (units labeled, zeros as dash, negatives in parentheses); one format per column
- [ ] One body font and size throughout; vary only by role (headers)
- [ ] Numbers right-aligned, text left, one vertical alignment in the data region
- [ ] Headers wrap via alignment, not hard line breaks inside cells
- [ ] One header fill/style across every sheet; total/subtotal rows (sum, add, or subtract formulas) bold and styled the same everywhere
- [ ] Color by role applied workbook-wide, not just the assumptions tab
- [ ] No layout merges; no text clipped (widen the column or wrap and raise the row)
- [ ] Column widths and row heights sized so all content is visible (they may vary; nothing clipped)
- [ ] No formatted number wider than its column (would show as ####)
- [ ] Freeze panes only on large scrollable sheets, consistent across tabs (or none)
```

## Dynamic scenarios and sensitivities

Scenario tables and sensitivity grids must stay live. Every interior cell
references the visible row driver and column driver that label its position, so
changing a driver flows through. A pre-computed number pasted into an interior
cell is a defect even when it currently matches: it breaks the moment a driver
changes, and it hides the relationship the table is supposed to show. A
sensitivity grid that does not move when you change its axis inputs is wrong by
construction.

## Schedules must reconcile to their timing

Lease-up, debt amortization, depreciation, and any other time-based schedule
must show the intervening logic period by period. A schedule cannot jump from an
initial value to a stabilized or terminal value with no rows between. Occupancy
that steps from 60 percent to a stabilized 94 percent must show each period's
absorption. A loan balance must amortize period by period to its maturity
balance. If the schedule reconciles end to end only because a terminal cell is
hardcoded, the timing is not modeled.

## Formats, labels, and units

A correct number presented ambiguously gets misread, and a misread number costs
the same trust as a wrong one. Make the format, label, and unit carry the
meaning so a business user cannot confuse:

- dollars with rates: `$#,##0` versus `0.0%`, never a raw decimal for a rate.
- monthly with annual: say so in the label ("Monthly Rent", "Annual Debt
  Service"), do not leave the period to inference.
- per-unit with aggregate: label the basis ("Revenue per Unit" versus "Total
  Revenue ($mm)") and keep the two out of the same column.

State units in the header whenever a column's scale is not obvious from its
cells.

## Severity ordering

When you must choose what to fix first, integrity outranks presentation. A
wrong-cell reference, a static paste, a number stored as text, or a unit
mismatch is a defect. Font, color, and spacing are finishing. Never let a
presentation pass ship while an integrity defect remains, and never report a
model as clean on the strength of its formatting.
