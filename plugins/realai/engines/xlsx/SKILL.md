---
name: xlsx
description: "Use this skill any time a spreadsheet file is the primary input or output. This means any task where the user wants to: open, read, edit, or fix an existing .xlsx, .xlsm, .csv, or .tsv file (e.g., adding columns, computing formulas, formatting, charting, cleaning messy data); create a new spreadsheet from scratch or from other data sources; or convert between tabular file formats. Trigger especially when the user references a spreadsheet file by name or path, even casually (like \"the xlsx in my downloads\"), and wants something done to it or produced from it. Also trigger for cleaning or restructuring messy tabular data files (malformed rows, misplaced headers, junk data) into proper spreadsheets. The deliverable must be a spreadsheet file. Do NOT trigger when the primary deliverable is a Word document, HTML report, standalone Python script, database pipeline, or Google Sheets API integration, even if tabular data is involved."
license: Proprietary. LICENSE.txt has complete terms
---

# Contents

- Formulas First: the non-negotiables (read this first)
- Requirements for Outputs: integrity rules, then formatting rules
- Workflows: how to build, edit, read, and analyze (routes to the reference files below)
- Citation Contract: how to cite cells so the viewer resolves them
- Output Rules: what must and must not appear in the final response

Reference files, read on demand for the task at hand:
- [references/model-integrity.md](references/model-integrity.md): the error-free-but-wrong failure catalog, the integrity scan categories, and the review checklists.
- [references/building-and-editing.md](references/building-and-editing.md): creating and editing workbooks, recalc, formula verification, library and code-style notes.
- [references/reading-and-analysis.md](references/reading-and-analysis.md): the large-workbook profile, scan, sample, extract, search, and trace workflow, the claims ledger, and the anti-smoothing protocol.

# Formulas First: the non-negotiables

These four rules outrank everything else in this skill. Apply them on every workbook, then move to the detailed rules below.

1. **Live and auditable, not just polished.** Every calculated output pulls from the model via formulas, so the workbook updates when an assumption changes. Calculate in Excel, not in Python-then-paste. See [references/building-and-editing.md](references/building-and-editing.md).

2. **Error-free is not correct.** A workbook with zero Excel errors can still be wrong: a formula points at the wrong cell, reads through an empty header, pulls a similarly named metric, or sits on a value pasted over a formula. This silent class is the primary failure mode and most of your attention belongs here. See "Error-Free Is Not Correct" and [references/model-integrity.md](references/model-integrity.md).

3. **Assumptions live in input cells, never baked into formulas.** Every rate, margin, multiple, and factor is a labeled input cell referenced with a locked address. Scenario and sensitivity interiors reference their row and column drivers so the grid moves when a driver changes.

4. **Integrity outranks presentation.** Fix wrong references, static pastes, numbers-as-text, and unit mismatches before any formatting pass. Never report a model as clean on the strength of its formatting.

**Gate every model you build or edit.** Run the integrity scan, fix HIGH findings, then recalc:

```bash
python skills/xlsx/scripts/workbook_integrity_scan.py output.xlsx && \
python skills/xlsx/scripts/recalc.py output.xlsx
```

Check the gate by the **exit code** (non-zero means HIGH findings) or the `GATE: PASS/FAIL` line on stderr. Do NOT grep the JSON for a severity string: severities are lowercase (`"high"`), so a case-mismatched grep matches nothing and makes a failing model look clean. The `&&` above only runs recalc if the scan passed.

# Requirements for Outputs

## All Excel files

### Professional Font
- Use a consistent, professional font (e.g., Arial, Times New Roman) for all deliverables unless otherwise instructed by the user

### Zero Formula Errors
- Every Excel model MUST be delivered with ZERO formula errors (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)
- Zero errors is necessary but NOT sufficient. A clean recalc proves the formulas run, not that they compute the right thing. See the next rule.

### Error-Free Is Not Correct (Structural Integrity)
This is the most important rule in this skill and carries the most weight. A workbook with zero Excel errors can still be wrong, and that silent failure is what loses customer trust because the file looks finished. The error-free-but-wrong defects you MUST catch:
- A formula that points at the wrong cell (a total summing B2:B9 when the data runs B2:B12, or an off-by-one range).
- A reference that resolves through an empty header row, silently returning the wrong column.
- Metric identity confusion: the label names one metric and the formula computes another. Watch the near-synonym swaps (gross vs effective, leased vs physical occupancy, margin vs ratio, value-over-cost vs value-over-rate, cap rate vs yield-on-cost), and the same metric computed two different ways on two sheets. Read the adjacent label and confirm the formula computes that exact concept, not just a plausible neighbor.
- A static value pasted over a formula, so a projection period no longer recalculates. Sensitivity and scenario tables are the worst offenders, but it also hides in adjustment grids, stat blocks, summary rows, and cover figures: anything that should move when an input changes but doesn't.
- An assumption baked into a formula instead of referenced from an input cell.
- A unit or scale mismatch (monthly times an annual rate, per-unit mixed with aggregate) that computes cleanly and means nothing.
- Disconnected or orphaned logic: a schedule that computes but feeds nothing, an assumption defined but never referenced, or a surface whose own numbers contradict an assumption used elsewhere. These are missing connections, not wrong ones, and they are easy to miss.
- Derived values pasted as numbers, even outside a pro forma. A comps adjustment grid (total adjustment, adjusted rent, implied premium/discount), an average, a per-SF or per-unit figure, a ratio: if it is computed from other cells it must be a formula. Raw imported data (a comp's address, asking rent, square footage) is fine to hardcode; the analysis built ON that data is not. A whole workbook with no formulas anywhere is a dead analysis no matter how clean it looks, and recalc reporting zero total formulas is the tell.

Every workbook must be live and auditable, not just visually polished: calculated outputs pull from the model via formulas so results update when assumptions change.

Run the integrity scan to surface the silent defects recalc cannot see, then fix every HIGH-severity finding before delivery:
```bash
python skills/xlsx/scripts/workbook_integrity_scan.py <file.xlsx> --json output/integrity.json
```
It flags, on the structural side, numbers stored as text, computed sheets that are entirely hardcoded (a pro forma or schedule with no formulas), whole workbooks with no formulas at all, derived analysis cells pasted as values (an adjustment grid, implied premium, margin), static pastes inside formula runs, blank table headers, cached errors, references to empty cells (a wrong reference buried in arithmetic, like a rate pulled from a blank row so vacancy reads zero), label/link mismatches (a link cell whose row label does not match the cell it points at, which catches the off-by-one summary cascade and the wrong-but-plausible cross-sheet reference), and (advisory) assumptions baked into formulas and orphaned defined names; and on the presentation side, stray symbols in cells, body-grid merges, formula cells colored as inputs, and likely-truncated columns. The scan is a net, not a substitute for reading the model: it still cannot catch a wrong reference between two unlabeled cells, or the same metric computed two different ways on two sheets. Those need the reconciliation below.

For the full failure catalog, the integrity review checklist, and fix patterns, see [references/model-integrity.md](references/model-integrity.md).

### Reconcile Before Delivery (catches what the scan cannot)
A clean scan and zero errors are not a pass. The defects that ship anyway are the ones no tool flags: a summary that links to a plausible neighbor, a headline metric computed one way on one sheet and another way elsewhere, a sensitivity table that does not actually move. Before delivery, reconcile:
- **Label-to-link reconciliation.** For every cross-sheet summary or link cell, confirm the label beside it names the same metric as the cell it points at. The `label_link_mismatch` scan finding does most of this; for links the scan cannot label-match, trace them with `workbook_trace.py --cell` and read both ends. A cluster of these in one column means a whole block is shifted; fix the block, do not patch one cell.
- **Independent recompute of headline outputs.** Recompute NOI, EGI, value, development yield, DSCR, and any go/no-go metric from the inputs yourself (a claims ledger, see the reading reference) and assert each ties to the cell the workbook displays. This is what catches a metric computed two ways: if your independent EGI-minus-OpEx does not equal the displayed NOI, one of them is wrong.
- **Narrate the workbook, never your Python.** Every number you state in prose MUST be read back from the recalculated workbook cell, not from a Python variable you computed during the build, and MUST carry a citation. Reading back to verify is not enough; you also have to cite. Follow "Cite Headline Figures" in the Citation Contract (save to library for the `file_id`, then register a citation per figure with `file_id` + sheet-qualified `cell_range` + the read-back value). This is the step that gets skipped: a figure narrated from memory silently disagrees with the cell the reader clicks, and the same metric can end up stated three different ways across the file. A derived read with no cell behind it (a breakeven, a solved-for basis, a target price range you computed in your head from cells) is the same failure arrived at honestly: add the formula to the workbook, recalc, and cite the cell - or cut the figure from the response.
- **Single source per metric.** A metric must be computed once and referenced everywhere else. If an expense ratio, cap rate, or cost basis appears on two sheets, they must be the same cell reference or tie exactly. A benchmark stated anywhere (a label or header, for example "should match ~44%") must equal what the cells actually compute. Denominators are metrics too: a unit count or square footage is one input cell referenced everywhere, and a sourced figure arriving on a different basis (a data-source NOI covering 399 units against a stated 400) is reconciled or disclosed at the figure, never silently divided against the other basis. Rows a reader will compare side by side (a GP total against an LP total) must include the same components - both with return of capital or both without - and each row's label states exactly what its formula includes.
- **Sensitivity tables must move.** Change a row driver and a column driver and confirm the interior recomputes. An interior cell that bakes its axis values as literals (a cluster of `formula_literal` advisories on a sensitivity sheet is the tell) is decorative, not dynamic; rebuild it to reference the axis headers. And a scenario table delivers every column its headers promise: a Low/Base/High header row with only the Base column populated shows the reader a three-scenario table that delivers one - populate every scenario for every row, or drop the headers the row does not fill.
- **Displayed structure must drive the math.** Any schedule, tier table, or driver block shown on a sheet must feed the calculation it illustrates. A promote tier schedule the distribution math never references, computed instead from a flat blended-rate input beside it, is decorative: the sheet displays one methodology and computes another. Wire the structure in (compute through the tiers) or remove it. Check with `workbook_trace.py --orphans` and by tracing each headline output's precedents back to the blocks the sheet displays.

**Integrity outranks presentation.** A wrong-cell reference, a static paste, a number stored as text, or a unit mismatch is a defect. Font, color, and spacing are finishing. Presentation defects NEVER outweigh integrity defects: never ship a formatting pass while an integrity defect remains, and never report a model as clean on the strength of its formatting.

### Preserve Existing Templates (when updating templates)
- Study and EXACTLY match existing format, style, and conventions when modifying files
- Never impose standardized formatting on files with established patterns
- Existing template conventions override these guidelines, with ONE exception: do not preserve a convention that creates a static output where a formula belongs, a misleading format or unit, or a wrong formula. Fix those even when matching the template; integrity outranks consistency.

### Cell Content and Layout Hygiene
A clean grid that a formula can address reliably matters as much as a clean number, and consistency across the workbook is what separates a professional model from a junior one. The `stray_symbol`, `merged_cells`, `narrow_column`, `clipped_row`, `number_too_wide`, `freeze_panes`, `font_consistency`, `embedded_newline`, `number_format`, `alignment`, `total_row_style`, and `header_style` checks in the integrity scan surface these; resolve them before delivery.
- **No stray symbols in cells.** Cells hold words and numbers, not decoration. Do not put emoji, status icons, arrows, bullets, or em and en dashes in a cell where text belongs: use words or a plain hyphen. Do not use math-operator glyphs (x, /, >=, +/-) as text; write the word or the ASCII operator.
- **Numbers stored as numbers.** Rates, occupancy, prices, and counts are numeric cells, never strings. A value typed as text reads fine and silently drops out of every calculation that references it. See "Numbers stay numeric" below.
- **One number format per column.** A column of numbers carries one format down its whole length. Do not leave some cells formatted ($#,##0) and others raw (General); a mix reads as unfinished. Counts, years, dollars, rates, and multiples each get the format the "Number Formatting Standards" below prescribe.
- **Consistent fonts.** Pick one body font and one body size and use them everywhere; vary only by role (bold or larger for headers and section titles). Do not let body text drift between 9, 10, and 11 point across or within sheets. Mixed body sizes are the clearest amateur tell.
- **Consistent alignment.** Right-align numbers (or leave them at default, which right-aligns), left-align text labels, and use one vertical alignment (usually center) for the data region. Do not center numbers on one sheet and left-align them on another, and do not mix top, center, and bottom vertical alignment within a table.
- **One header style across the whole table set.** Every table and section header uses the same fill and font treatment on every sheet. Do not shade headers on one tab and leave them plain on another, or use a different header blue on each sheet. At most one primary header fill plus one subheader fill, applied consistently.
- **Distinguish total rows, consistently.** A total or subtotal row (any row whose formula combines other rows, whether by SUM, SUMIFS, SUMPRODUCT, COUNTIFS, an INDEX wrapping a sum, or plain addition and subtraction like EGI minus expenses) is visually set off the same way everywhere: bold, often with a top border. Do not leave a total row looking like a body row, and do not style totals differently from sheet to sheet.
- **Row heights show the content.** Size each row tall enough to display its text, and let heights vary as needed (a wrapped text row is taller than a single-line row; that is correct, not a defect). The defect is a fixed row height too short for its wrapped text, which clips it. If a cell wraps, give its row the height to show every line, or let the row auto-size.
- **Minimal merging.** Do not merge cells for layout. A merge that spans rows, or spans columns inside the data body, breaks sorting, filtering, copy-paste, and formula references, and fragments a grid a formula cannot reliably address. Use a wider column, a centered header, or center-across-selection instead. A single-row title banner across the top is the only routine acceptable merge.
- **Wrap headers, do not hard-break them.** For a multi-line header, set wrap-text alignment on the cell and store a single string. Do not type a hard line break (alt-enter) inside the cell to fake wrapping; it breaks at a fixed point and looks ragged when the column is resized.
- **Column widths show the content.** Size each column so its content is fully visible, and let widths vary as needed (a label column is wider than a rate column; that is correct, not a defect). The defect is text shoved together: a value wider than its column whose neighbor is occupied, so it is cut off. Widen that column, or wrap the text and raise the row height. A long label that overflows into an empty cell is fine.
- **Numbers must fit, or they show as ####.** Unlike text, a formatted number does not overflow into the next cell; if it is wider than its column it renders as `####` and the value is invisible in the preview. Size the column to fit the formatted number (including the currency symbol, thousands commas, decimals, and a minus or parentheses). The `number_too_wide` scan flags these.
- **Freeze panes only where they earn it.** Freeze panes belong on large sheets that actually scroll, frozen once at the header-and-label boundary (for example the row below the headers and the column right of the labels). Do not freeze a sheet that fits on screen, and use the same freeze convention on every sheet that needs one. Inconsistent freeze points across tabs look careless.
- **Tab color signals meaning or nothing.** If you color worksheet tabs, the colors must encode a real structure (for example inputs vs outputs vs checks) and hold to it across the whole workbook. Do not color tabs decoratively or inconsistently: a color scheme that implies a convention the file does not keep is worse than no color.

## Financial models

### Color Coding Standards
Unless otherwise stated by the user or existing template

#### Industry-Standard Color Conventions
- **Blue text (RGB: 0,0,255)**: Hardcoded inputs, and numbers users will change for scenarios
- **Black text (RGB: 0,0,0)**: ALL formulas and calculations
- **Green text (RGB: 0,128,0)**: Links pulling from other worksheets within same workbook
- **Red text (RGB: 255,0,0)**: External links to other files
- **Yellow background (RGB: 255,255,0)**: Key assumptions needing attention or cells that need to be updated
- Color by ROLE, not by location. A cell's color follows what it is (hardcoded input, formula, cross-sheet link, external link), never where it sits. Do not leave hardcoded inputs black, do not color formulas blue, and do not leave cross-sheet links un-greened. The common failure is applying the convention to the assumptions tab only: it must hold on every sheet.
- Apply this coding workbook-wide and consistently, not sheet by sheet. The same cell role gets the same color on every sheet, so a reviewer can tell an input from a formula from a cross-sheet link at a glance anywhere in the file. The integrity scan flags formula cells colored blue (an input color) as a `color_role` finding.

### Number Formatting Standards

#### Required Format Rules
- **Numbers stay numeric**: A calculated quantity is a numeric cell with a number format, NEVER a text string used to control presentation. Store the number and apply a format ("$24.0M" comes from a number format on a numeric cell, not from typing the literal text "$24.0M"). A text string that looks like a number breaks every formula that references it and is a defect, not a style choice.
- **Years**: Format as text strings (e.g., "2024" not "2,024")
- **Currency**: Use $#,##0 format; ALWAYS specify units in headers ("Revenue ($mm)")
- **Zeros**: Use number formatting to make all zeros "-", including percentages (e.g., "$#,##0;($#,##0);-")
- **Percentages**: Default to 0.0% format (one decimal)
- **Multiples**: Format as 0.0x for valuation multiples (EV/EBITDA, P/E)
- **Negative numbers**: Use parentheses (123) not minus -123

#### Labels and Units Must Prevent Misreading
The format, label, and unit must make the meaning unambiguous so a business user cannot misread dollars as rates, monthly as annual, or per-unit as aggregate:
- Dollars versus rates: format dollars as $#,##0 and rates as 0.0%; never present a rate as a bare decimal.
- Monthly versus annual: state the period in the label ("Monthly Rent", "Annual Debt Service"); do not leave it to inference.
- Per-unit versus aggregate: label the basis ("Revenue per Unit" versus "Total Revenue ($mm)") and keep the two out of the same column.
- A correct number presented ambiguously costs the same trust as a wrong one.

### Formula Construction Rules

#### Assumptions Placement
- Place ALL assumptions (growth rates, margins, multiples, etc.) in separate, labeled input cells
- Reference those cells with LOCKED addresses ($B$6) so fills and copies do not drift the reference
- An assumption is NEVER baked as a literal inside a formula. The growth rate, margin, or multiple lives in an identifiable input cell and the formula points at it.
- Label an assumption's basis, not only its value. An input resting on analyst judgment (a pass-through rate, a capture haircut, a contingency) sits beside sourced inputs looking equally grounded unless the label or an adjacent note says otherwise. The unlabeled judgment input is often the most influential number in the model, so it is the one a reviewer most needs flagged.
- Example: Use =B5*(1+$B$6) instead of =B5*1.05

#### Lock Shared Anchors with $
- When a column or row of formulas all reference the SAME fixed cell (an EGI total, a units count, a cap-rate input), lock the dimension that should not move: `D$9` to hold a row, `$C$6` to hold both. Otherwise a fill drifts each formula onto a different cell and the values go silently wrong.
- Cross-sheet references to a single input (`Assumptions!$C$6`) are almost always meant to be fixed; lock them. The `unlocked_anchor` scan flags an anchor referenced by a run of formulas without a lock.
- Verify a referenced cell is the intended, populated input. A formula that multiplies by a blank cell (a rate pulled from the wrong row) silently yields zero and reads as error-free; the `blank_reference` scan flags this.

#### Scenarios and Sensitivities Stay Dynamic
- Scenario tables and sensitivity grids must recalculate. Every interior cell references the visible row driver and column driver that label its position, so changing a driver flows through.
- A pre-computed number pasted into an interior cell is a defect even when it currently matches: it breaks the moment a driver changes and hides the relationship the table exists to show. A sensitivity grid that does not move when you change its axis inputs is wrong by construction.
- Two or more independent uncertain drivers feeding one output get a cross-product grid, not a set of one-at-a-time tables. Varying cost while capture rate sits at base, then capture rate while cost sits at base, tests neither corner: the case that breaks a thesis is usually both drivers moving against you at once, and a pair of marginal tables hides it while looking thorough. Where a full grid is more than the model warrants, compute the single worst plausible combination anyway.
- Report the cell where the verdict flips. If any scenario in the grid takes a yield under the market cap rate, a DSCR under its covenant, or a return under the threshold, name that combination in the response instead of reporting only the range that clears. A grid built solely from the scenarios that keep the thesis intact is a presentation, not a test.

#### Schedules Reconcile to Their Timing
- Lease-up, debt amortization, depreciation, and any other time-based schedule must show the intervening logic period by period. A schedule cannot jump from an initial value to a stabilized or terminal value with no rows between.
- Occupancy stepping from 60 percent to a stabilized 94 percent must show each period's absorption; a loan balance must amortize period by period to its maturity balance. If a schedule reconciles end to end only because a terminal cell is hardcoded, the timing is not modeled.
- Cumulative counts cap at their physical limit. A running lease-up or unit count cannot exceed total units; a cumulative percentage cannot exceed 100. Bound the cumulative formula so it stops at the limit.
- A terminal or stabilized column must tie to the periods shown, not float free of them. The stabilized figure equals what the period-by-period schedule produces at stabilization.
- Watch for double-counting across rows. Each row can look correct in isolation while a subtotal counts the same dollars or units twice (a cost included in both a line item and an allocated total, a unit counted in two cohorts). Verify the components of every subtotal are mutually exclusive before trusting it.

#### Formula Error Prevention
- Verify all cell references are correct
- Check for off-by-one errors in ranges
- One index source per table. When a script writes a labeled series, the header text and its value cell derive from the same index variable, never from two expressions in separate loops (`1+i` for the header, `2+i` for the value). That drift shifts every column one slot from its own header, spills the last period past the table edge, and still passes recalc and the scan because each formula remains internally consistent.
- Assert the written range against its source array. After a script writes an engine-returned or computed series into a sheet, read the range back and assert it matches the source element for element before saving. A whole-array assertion fails loudly on the first run; spot-checking one summary cell that happens to reference the right column does not.
- Ensure consistent formulas across all projection periods
- Test with edge cases (zero values, negative numbers)
- Verify no unintended circular references

# Workflows

Pick the path for the task. The detailed steps and code live in the reference files; this section routes you there and names the scripts.

## Building or editing a workbook

Calculate in Excel, not in Python-then-paste (see Formulas First). Use openpyxl for formulas and formatting, pandas for bulk data. Editing an existing file has its own hazards (preserve conventions, do not introduce static pastes, scan before and after); follow the Edit path in the reference.

Full how-to: [references/building-and-editing.md](references/building-and-editing.md).

Mandatory gate before delivering or citing any workbook you created or changed:

```bash
python skills/xlsx/scripts/workbook_integrity_scan.py output.xlsx && \
python skills/xlsx/scripts/recalc.py output.xlsx
```

Fix every HIGH-severity scan finding and every formula error to zero. To confirm a formula references what you intend, trace it: `workbook_trace.py --cell "Sheet!B10"`.

Fix in batches, not one edit per finding. Collect every finding from a scan pass, apply them all in one scripted pass (openpyxl), then rescan once; a finding-by-finding edit cycle is the slowest possible shape for the same result. Better still, spend the fixes upfront: column widths, number formats, fonts, and color roles belong in the initial build script, not in a repair pass after the scan flags them.

## Reading, auditing, or analyzing a workbook

Do not dump every cell. Profile, scan, sample, then extract only what is needed. For quantitative analysis, the claims ledger and the anti-smoothing protocol are required before any narrative.

Full how-to: [references/reading-and-analysis.md](references/reading-and-analysis.md).

## Scripts

All scripts print JSON and are read-only except recalc.py (which writes recalculated values back). Run from the repo root.

- `workbook_profile.py <file>`: size tier, per-sheet shape, formula counts, tables, defined names.
- `workbook_integrity_scan.py <file>`: silent structural and presentation defects; HIGH findings exit non-zero. This is the build gate.
- `workbook_trace.py <file> --cell REF | --orphans`: precedents and dependents of a cell or range; unreferenced inputs, defined names, and terminal formulas.
- `workbook_sample.py <file>`: per-sheet value and formula CSV samples plus a manifest.
- `workbook_manifest_query.py <manifest>`: look up sample filenames; never guess them.
- `workbook_extract.py <file> --sheet ... --columns ...`: deterministic value and formula extraction windows.
- `workbook_search.py <file> --pattern ...`: regex search across values and formulas.
- `workbook_claims_schema_check.py <claims.json>` then `workbook_claims_check.py <claims.json>`: validate the claims ledger before narrative.
- `recalc.py <file>`: recalculate all formulas via LibreOffice and report Excel errors.

recalc.py assumes LibreOffice is installed and configures it on first run, including in sandboxes where Unix sockets are restricted (handled by `scripts/office/soffice.py`).

---

# Citation Contract

## Cite Headline Figures (required final step, do not skip)

Reading a value back to check your math is NOT the same as citing it, and verifying is not enough: every headline figure in your response (NOI, EGI, value, yield, cap rate, shortfall, carry, any go/no-go number) MUST be a citation anchored to the cell it came from. The number a reader sees in your prose has to be the number they land on when they click. This is the step that is consistently skipped; treat it as mandatory and do it last, before you send the response.

The chain, end to end:
1. Save the finished workbook to the library with `library_save`. It returns a `file_id` (a NEW file omits `file_id`; a new version passes the existing one). That returned `file_id` is what every citation needs.
2. Recalc (`recalc.py`) and reopen with `openpyxl(..., data_only=True)`. The value you read from each headline cell is the citation's `text_span` (the literal as it appears), and its address is the `cell_range`.
3. Register a citation (the endnotes/citation tool) for each headline figure with `location.file_id` (from step 1), `location.cell_range` (sheet-qualified, e.g. `Stabilized NOI!C29`), and `text_span` (the read-back value). One citation per figure you state.
4. Present the workbook with `library_present`, passing the same `file_id`. Saving is what gets you the `file_id` for citations; presenting is what puts the file in front of the user. A workbook you built, gated, and cited but never presented never reaches them. Do this on the turn that built or changed the workbook, whether or not the user asked for a file. If `library_present` is not among your tools, report the workbook in your results instead so the parent agent presents it.

Do not state a headline number sourced from a Python variable you computed during the build. If you cannot cite it to a cell, do not put it in the response. And the cell outranks every other citation target: once a figure lives in a saved workbook, cite `file_id` + `cell_range`, never the sandbox call or build script that computed it - a sandbox citation on a workbook-backed figure sends the reader to Python instead of the cell. Once the analysis has a workbook at all, a load-bearing figure computed on the side belongs in it as a labeled cell rather than cited to a script: splitting one set of numbers across sandbox and file citations makes the reader chase two sources.

## Citation fields

When you read or quote from a spreadsheet and the user might cite it, the
citation MUST carry two things: a `file_id` identifying which file, and a
`cell_range` anchoring to a specific cell (sheet-qualified for `.xlsx` / `.xlsm`
workbooks, bare for `.csv`). The in-app spreadsheet viewer uses `file_id` to
open the correct file, then reads `cell_range` to switch to the named sheet,
scroll to the cell, and highlight it. Other anchors (page numbers) do not work
for spreadsheets.

Rules:

- `file_id` is REQUIRED on every citation. It identifies which file the
  `cell_range` belongs to. Without it the viewer cannot resolve the citation,
  especially when more than one file is in play; a `cell_range` alone is
  ambiguous. Use the `file_id` of the workbook you actually read the value from.
- Use `location.cell_range` (NOT `location.page`). Spreadsheets have no pages.
- Sheet-qualify every workbook citation: `Assumptions!C9`, not `C9`.
- For `.csv` files, omit the sheet: `A1`, not `Sheet1!A1`.
- Prefer single-cell anchors (`C9`) over single-cell ranges (`C9:C9`). Use
  ranges only when the cited fact spans a contiguous block (a column total,
  a row of period totals).
- Pair `cell_range` with `text_span` (the literal value as it appears in the
  cell) so the citation pill can show the value inline.
- For sheet names containing apostrophes, double the apostrophe and wrap the
  whole name in single quotes: `'O''Brien Model'!A1`.

## Recalculate Before Citing Computed Cells

The viewer renders the workbook's **cached** values, the same values Excel
shows when it opens the file. If you read a value with pandas (or compute it
in Python) and cite a number that disagrees with what's stored in the cell,
the user clicks the citation and sees a different number. That looks broken
even when your math is correct.

Before citing any cell whose value comes from a formula, recalc the workbook
once:

```bash
python skills/xlsx/scripts/recalc.py file.xlsx
```

Then read the recalculated workbook (e.g. with `openpyxl(..., data_only=True)`)
and cite the value you see. Recalc once per session per workbook; the script
writes back to the same file, so subsequent reads pick up the updated cache.

## When to Convert to PDF

Never. Spreadsheets cite directly via `cell_range`. There is no PDF-conversion
flow for `.xlsx` / `.xlsm` / `.csv` because LibreOffice's pagination is
print-area driven and unreliable, and cell addresses are a more precise anchor
than a page number.

---

## Output Rules (Apply When Writing the Final Response)

These rules govern what must not appear in the response delivered to the user. Read them immediately before writing the output.

**Present before you reference.** If the response mentions a workbook or file you built or changed, `library_present` for it must already have run this turn. Citing a file is not presenting it: registering citations completes the audit trail, not the delivery, and a save with no present is an undelivered file the user never sees.

**Do not surface validation mechanics.** Statements like "All 7 claims pass validation", "X derived checks validated mechanically", "no discrepancies found in the model's headline figures", or "validation passed" are internal scaffolding. They belong in your reasoning, not in the response. The user cares about the substance: the numbers, what they mean, what the risks are. Internal consistency checks are assumed; announcing them adds noise and can give false confidence when minor issues remain.

**Do not announce the process.** Do not describe which scripts were run, how many sheets were sampled, or what the coverage manifest contained. Report findings, not method.

**Do not hedge with process gaps.** If a section of the model was not read, either go back and read it or explicitly omit it from the output scope. Do not write "I was unable to fully sample sheet X"; either cover it or don't mention it.

**Tables must be internally arithmetic-consistent.** When a table contains a row that is derived from other rows in the same table (e.g., NOI = EGI − Total Expenses), all per-unit or per-period figures in that table must be consistent with each other. Do not mix provenance modes within the same table, for example taking some per-unit values from the spreadsheet's displayed cells and others from aggregate ÷ N, without first verifying that all rows still add up. If a derived row's per-unit figure doesn't equal the arithmetic result of its component rows, resolve the discrepancy before presenting the table.

**Narrative prose must be consistent with tables in the same response.** Before finalizing the output, verify that every quantitative claim in the narrative text matches the numbers shown in the tables produced in the same response. Do not re-estimate a figure in prose that is already shown precisely in a table above it.
