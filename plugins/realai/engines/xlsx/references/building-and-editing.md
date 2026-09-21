# Building and Editing Workbooks

The Build and Edit path. Read this when creating a new workbook or modifying an
existing one. SKILL.md links here from the Workflows section. The rules in
SKILL.md (Formulas First, Requirements for Outputs) still govern; this file is
the how-to.

## Contents

- The mandatory gate (run on every build or edit)
- Use formulas, not hardcoded values
- Choosing a library
- Creating a new workbook
- Editing an existing workbook (the Edit path)
- Recalculating formulas
- Formula verification checklist
- Library notes (openpyxl, pandas)
- Code style

## The mandatory gate (run on every build or edit)

After you create or change a workbook, before you deliver or cite it, run the
integrity scan and the recalc, and fix what they surface:

```bash
python skills/xlsx/scripts/workbook_integrity_scan.py output.xlsx && \
python skills/xlsx/scripts/recalc.py output.xlsx
```

The scan fails the gate (non-zero) on any HIGH-severity finding; recalc reports
formula errors. Check the gate by the exit code or the `GATE: PASS/FAIL` line on
stderr, never by grepping the JSON for a severity string (severities are
lowercase `"high"`; a `"HIGH"` grep matches nothing and hides a failing model).
Fix both to zero before delivery. To verify a specific formula points where you
intend, trace it:

```bash
python skills/xlsx/scripts/workbook_trace.py output.xlsx --cell "Calc!B14"
```

Zero errors and a clean scan are necessary but NOT a pass. Before delivery also
run the Reconcile Before Delivery step in SKILL.md: confirm every cross-sheet
link's label matches its target (the scan's `label_link_mismatch` covers most of
this), independently recompute the headline outputs and assert they tie, keep one
source per metric, and confirm sensitivity tables actually move. A cluster of
`label_link_mismatch` findings in one column means a whole summary block is
shifted; fix the block, do not patch one cell and re-run. Fixing adjacent cells
while leaving the real defect is the most common way a broken model still ships
a clean recalc.

### Gate the file you actually deliver

Two process traps ship a model that you thought you fixed:

- **Re-scan after every rebuild.** Run the integrity scan on the EXACT file you
  hand over, as the last thing before delivery. recalc alone is not the gate.
  Scanning an earlier build, then rebuilding and shipping the rebuild unscanned,
  means the gate never saw the delivered artifact: every HIGH finding it would
  have caught ships with it.
- **Bake fixes into the build script, then rebuild once.** Do not edit the output
  workbook to fix a defect and then rebuild from scratch: the rebuild regenerates
  the file from the script and discards your edits. Put the correction in the
  build script (or the manifest), rebuild, then re-gate. Fix-the-output-then-
  rebuild loses every fix and reintroduces the defects you just corrected.

## Use formulas, not hardcoded values

Always use Excel formulas instead of calculating values in Python and hardcoding
them. This keeps the workbook live: results update when source data changes.

WRONG, hardcoding calculated values:
```python
total = df['Sales'].sum()
sheet['B10'] = total                       # hardcodes 5000

growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth                       # hardcodes 0.15

avg = sum(values) / len(values)
sheet['D20'] = avg                         # hardcodes 42.5
```

CORRECT, using Excel formulas:
```python
sheet['B10'] = '=SUM(B2:B9)'
sheet['C5'] = '=(C4-C2)/C2'
sheet['D20'] = '=AVERAGE(D2:D19)'
```

This applies to ALL calculations: totals, percentages, ratios, differences. The
spreadsheet must recalculate when its inputs change. Assumptions (rates, margins,
multiples) go in labeled input cells referenced with locked addresses
(`=B5*(1+$B$6)`), never baked as literals.

This is the single most common way a build script ships a dead model: it computes
NOI, EGI, yield, and the whole sensitivity grid in Python and writes the numbers
as literals. The result looks complete, recalcs without error, and is entirely
static. Write the formula string into the cell and let recalc compute the value;
do not assign a Python-computed number. The `hardcoded_outputs` scan fails any
computed sheet (pro forma, schedule, sensitivity) that has almost no formulas.

After recalc, read the headline outputs back from the workbook
(`load_workbook(..., data_only=True)`) and narrate and cite THOSE values, never
the Python variables you computed during the build. The two can disagree, and the
reader audits the cell, not your script.

## Choosing a library

- **pandas**: data analysis, bulk operations, simple data export.
- **openpyxl**: formulas, formatting, color, number formats, Excel-specific features.

Common workflow: choose tool, create or load, modify, save, recalc, verify.

## Creating a new workbook

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

sheet['B2'] = '=SUM(A1:A10)'

sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')
sheet.column_dimensions['A'].width = 20      # set widths so content is not truncated

wb.save('output.xlsx')
```

## Editing an existing workbook (the Edit path)

Editing carries hazards that creating from scratch does not. Follow this order:

1. **Scan first.** Run the integrity scan on the original so you know its
   existing defects and do not get blamed for them, and so you have a baseline.
2. **Study the conventions.** Match the existing format, number formats, color
   coding, and layout exactly. Existing template conventions override the default
   guidelines, with one exception: do not preserve a convention that creates a
   static output where a formula belongs, a misleading format or unit, or a wrong
   formula. Fix those even while matching the template.
3. **Edit with openpyxl** so formulas and formatting survive the round trip.
4. **Do not introduce static pastes.** When you fill or extend a region, write
   formulas, not computed values. A pasted number is the most common defect an
   edit introduces.
5. **Scan again and recalc.** Run the gate after editing. Compare the scan to
   your baseline; every new HIGH finding is something your edit introduced.

```python
from openpyxl import load_workbook

wb = load_workbook('existing.xlsx')          # preserves formulas and formatting
sheet = wb.active                            # or wb['SheetName']

for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]

sheet['A1'] = 'New Value'
sheet.insert_rows(2)
sheet.delete_cols(3)

new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

Note: `insert_rows` and `delete_cols` do NOT rewrite formula references in
openpyxl. After inserting or deleting, verify affected formulas with
`workbook_trace.py --cell` and recalc.

## Recalculating formulas

Files created or modified by openpyxl hold formulas as strings but no computed
values until recalculated:

```bash
python skills/xlsx/scripts/recalc.py output.xlsx [timeout_seconds]
```

The script sets up the LibreOffice macro on first run, recalculates every sheet,
scans all cells for Excel errors, and returns JSON with error locations and
counts. It works on Linux and macOS. Interpreting the output:

```json
{
  "status": "success",
  "total_errors": 0,
  "total_formulas": 42,
  "error_summary": {
    "#REF!": { "count": 2, "locations": ["Sheet1!B5", "Sheet1!C10"] }
  }
}
```

If `status` is `errors_found`, read `error_summary`, fix the cells, and recalc
again. Common errors: `#REF!` invalid reference, `#DIV/0!` division by zero,
`#VALUE!` wrong data type, `#NAME?` unrecognized name.

## Formula verification checklist

Essential verification:
- [ ] Test 2-3 sample references against the cells they should hit before building the full model
- [ ] Confirm column mapping (column 64 = BL, not BK)
- [ ] Remember rows are 1-indexed (DataFrame row 5 = Excel row 6)

Common pitfalls:
- [ ] NaN handling: check nulls with `pd.notna()`
- [ ] Far-right columns: full-year data often sits in columns 50+
- [ ] Multiple matches: search all occurrences, not just the first
- [ ] Division by zero: check denominators (#DIV/0!)
- [ ] Wrong references: verify every reference points where intended (#REF! or, worse, a clean wrong number; use `workbook_trace.py`)
- [ ] Cross-sheet references: use `Sheet1!A1` form

Testing strategy:
- [ ] Start small: test formulas on 2-3 cells before applying broadly
- [ ] Verify every referenced cell exists
- [ ] Test edge cases: zero, negative, very large values

## Library notes

openpyxl:
- Cell indices are 1-based (row=1, column=1 is A1).
- `data_only=True` reads cached computed values: `load_workbook('f.xlsx', data_only=True)`.
- WARNING: opening with `data_only=True` and saving replaces formulas with values permanently.
- Large files: `read_only=True` to read, `write_only=True` to write.
- Formulas are preserved but not evaluated; use recalc.py to update values.

pandas:
- Specify dtypes to avoid inference issues: `pd.read_excel('f.xlsx', dtype={'id': str})`.
- Read specific columns on large files: `pd.read_excel('f.xlsx', usecols=['A','C','E'])`.
- Parse dates: `pd.read_excel('f.xlsx', parse_dates=['date_column'])`.

## Code style

When generating Python for Excel operations: write minimal, concise code without
unnecessary comments, verbose names, or stray print statements.
