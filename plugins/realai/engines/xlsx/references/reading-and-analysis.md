# Reading and Analyzing Workbooks

The Read path. Read this when opening a workbook to read, audit, or summarize it,
especially a large one or a quantitative model. SKILL.md links here from the
Workflows section. For citing values back to the user, see the Citation Contract
in SKILL.md; for the integrity failure catalog, see
[model-integrity.md](model-integrity.md).

## Contents

- Reading data with pandas
- Large workbook workflow (profile, scan, sample, extract, search, trace)
- Verifying references with the tracer
- Building a claims ledger
- Anti-smoothing protocol (required before final narrative)
- Hard rules for large files
- Inspecting workbook structure

## Reading data with pandas

```python
import pandas as pd

df = pd.read_excel('file.xlsx')                     # first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # dict of all sheets

df.head()
df.info()
df.describe()
```

## Large workbook workflow (profile, scan, sample, extract, search, trace)

When a spreadsheet is large, do not start by dumping every cell. Profile, scan,
then sample, then extract only what is needed. This workflow is mandatory for
large and very large workbooks and recommended for medium ones. For quantitative
analyses (model reviews, underwriting checks, deal summaries), the anti-smoothing
protocol below is required regardless of size.

### Step 1: Profile size and shape

```bash
python skills/xlsx/scripts/workbook_profile.py <file.xlsx>
```

Returns JSON: file size and size tier (`small`, `medium`, `large`,
`very_large`), per-sheet dimensions, non-empty row count, formula count, merged
cell count, Excel tables, workbook-level defined names with destinations, and
recommended next actions. For files >= 100MB the profiler short-circuits to
`very_large` without walking cells; run `workbook_sample.py` directly then.

### Step 1b: Early integrity scan

Before sampling content, run the integrity scan to surface silent defects,
especially static pastes (hardcoded values where formulas belong). Catching
these early changes how you read the rest of the model:

```bash
python skills/xlsx/scripts/workbook_integrity_scan.py <file.xlsx> --json output/integrity.json
```

Scope to specific sheets on very large files with `--sheets "Inputs,Calc"`.
Treat HIGH-severity findings as facts to verify and explain in the audit, not
noise to skip. See [model-integrity.md](model-integrity.md) for each category.

### Step 2: Create lightweight sheet samples

```bash
python skills/xlsx/scripts/workbook_sample.py <file.xlsx> --rows-per-sheet 10
```

Writes per-sheet CSV samples (default `output/samples/`) and a manifest JSON.
Default mode `--mode=both` produces two CSVs per sheet, one with computed values
(`*.values.sample.csv`) and one with formula text (`*.formulas.sample.csv`);
prefer `both`, the formula view shows how the model is wired. Default strategy
`--strategy=auto` switches to stratified sampling (head, spaced middles, tail)
for sheets larger than the row budget. Filenames are prefixed with the 1-based
sheet index (`01_`, `02_`) to avoid collisions.

Do not guess sample filenames. Query the manifest:

```bash
python skills/xlsx/scripts/workbook_manifest_query.py output/samples/sample_manifest.json --list
python skills/xlsx/scripts/workbook_manifest_query.py output/samples/sample_manifest.json --sheet "Inputs & Assumptions"
```

### Step 3: Targeted extraction

Read only required sheets and columns. Prefer bounded reads (`usecols`, `nrows`,
`skiprows`, chunking). Write intermediate outputs to files; print concise
summaries. For deterministic windows:

```bash
python skills/xlsx/scripts/workbook_extract.py <file.xlsx> --sheet "Sheet1" --start-row 2 --end-row 5000 --columns A:C,F --output output/extract.csv
```

`--mode` (xlsx/xlsm) defaults to `both`, splitting the output into
`output/extract.values.csv` and `output/extract.formulas.csv`. For CSV/TSV,
numeric column ranges work and mode is always `values`:

```bash
python skills/xlsx/scripts/workbook_extract.py <file.csv> --start-row 1 --end-row 100000 --columns 1-4,8 --output output/extract.csv
```

### Searching for terms

To locate a term, a defined name, or a cross-sheet reference, use regex search
instead of eyeballing samples:

```bash
python skills/xlsx/scripts/workbook_search.py <file.xlsx> --pattern "fee" --in both --limit 100
python skills/xlsx/scripts/workbook_search.py <file.xlsx> --pattern "Inputs!\$B" --in formulas
python skills/xlsx/scripts/workbook_search.py <file.xlsx> --pattern "cap.?rate" --sheets "Assumptions,Calc"
```

Returns cell-level matches with sheet, coordinate, computed value, formula text,
and which view matched. Case-insensitive by default; `--case-sensitive` to override.

## Verifying references with the tracer

recalc and the integrity scan cannot see a wrong-but-plausible reference: a total
that swept the wrong range, a formula one column off, a metric reading a similar
neighbor. Trace the cell to read what it actually references:

```bash
python skills/xlsx/scripts/workbook_trace.py <file.xlsx> --cell "Calc!B14"
```

Reports precedents (what the formula references, ranges and named ranges
resolved) and dependents (every formula that references the target). Read the
precedents against intent: a total whose range covers 8 cells when the data runs
12 periods is the defect. For disconnected logic, list orphans:

```bash
python skills/xlsx/scripts/workbook_trace.py <file.xlsx> --orphans
```

Reports unreferenced inputs (values no formula reads), unreferenced defined
names, and terminal formulas (results nothing consumes; expected for true
outputs, so review rather than assume defects). An assumption with zero
dependents is dead; a missed projection period often shows up here as an
unreferenced input.

## Building a claims ledger

Before writing narrative, create `output/claims.json` with raw `facts` (each with
an explicit source reference) and derived `claims` (expressions tied to facts via
`based_on_facts`). A claim with an `expected` field doubles as an executable
check; `workbook_claims_check.py` derives checks from every claim that has
`expected`, keeping the expression and its provenance together. Never build the
final narrative from a hardcoded metric dictionary without source mapping.

Tolerance is ABSOLUTE (`math.isclose(..., abs_tol=tolerance, rel_tol=0)`). For
`expected: 1500000, tolerance: 0.01`, pass means within one cent of 1,500,000.
For relative tolerance, scale it yourself (`tolerance: 150` for 0.01% of 1.5M).

Schema:

```json
{
  "values": { "fee_old": 0.025, "fee_new": 0.03 },
  "facts": [
    { "id": "fact_fee_old", "label": "Old mgmt fee", "value": 0.025,
      "source_sheet": "Inputs & Assumptions", "source_range": "D42",
      "extraction_method": "workbook_extract" },
    { "id": "fact_fee_new", "label": "New mgmt fee", "value": 0.03,
      "source_sheet": "Inputs & Assumptions", "source_range": "D43",
      "extraction_method": "workbook_extract" }
  ],
  "claims": [
    { "id": "claim_fee_spread_bps", "name": "fee_spread_bps",
      "expr": "(fee_new - fee_old) * 10000", "expected": 50, "tolerance": 0.01,
      "based_on_facts": ["fact_fee_old", "fact_fee_new"],
      "derivation": "(new fee - old fee) * 10,000" }
  ]
}
```

Validate, in this mandatory order, then write the narrative:

```bash
python skills/xlsx/scripts/workbook_claims_schema_check.py output/claims.json
python skills/xlsx/scripts/workbook_claims_check.py output/claims.json
```

The schema validator parses every `expr` and verifies referenced variables exist
in `values`, catching typos (`fee_olt` vs `fee_old`) at schema time.
`workbook_claims_check.py` exits non-zero when any check fails, so it chains with
`&&`. If a critical check fails, do not present the claim as fact: fix it or mark
it uncertain and explain why.

## Anti-smoothing protocol (required before final narrative)

To prevent polished-but-wrong summaries, complete this sequence before writing
conclusions:

1. **Coverage manifest.** Enumerate every major information layer (inputs, unit
   economics, operating assumptions, scenario comparisons, multi-period
   projections, comparable data, debt structure, return metrics). Layers are
   conceptual, not structural: one sheet can hold several. A "Rent Analysis"
   sheet may hold a unit mix table, an SFR comparables table, and a BFR
   comparables table; those are three layers, each needing independent
   confirmation. Confirming a sheet was read does not satisfy the manifest for
   layers within it not separately extracted. For each layer, note the sheet and
   range it came from. List any skipped layer and why; do not proceed with unread
   layers that belong in the output.

2. **Workbook map.** List major sheets and each sheet's role (inputs,
   calculations, outputs, checks).

3. **Mechanical drill-down.**
   - Timeline alignment: for every period-indexed metric, record the column index
     read from alongside the human period label ("Year 3 = column 23, header row
     4"). Read period labels from the header row; do not infer from context.
   - Unit/count tables: count enumerable items directly from the source range,
     not from memory. State the source range and the count.
   - Key metrics: verify debt and return metrics with their period label attached
     and column source recorded.

4. **Validate derived claims.**
   - Compute each derived claim (bps deltas, growth rates, ratios, per-unit
     figures) from extracted values and compare to your narrative.
   - Dual provenance: for any metric the spreadsheet itself displays in a cell,
     read that cell as a separate fact and reconcile it with your derivation. If
     they differ, flag and explain; do not silently pick one.
   - Multi-scenario models: build claims for both the prominent component-level
     delta and the net total difference across all line items. When citing a
     scenario's impact on a derived metric (cap rate, yield on cost, IRR), the NOI
     basis for that metric must equal the NOI basis used to state the impact; do
     not cite a fee-line delta as the NOI impact alongside a cap rate derived from
     full-scenario NOI. Use one consistent NOI basis per scenario claim.
   - Use `workbook_claims_check.py` for this step.

Operational guardrails: do not summarize from memory of sampled tables; do not
use ad hoc constants without a source location; prefer small targeted extracts
per claim over broad `cat` dumps; do not truncate machine-readable outputs
(`tail -20` on JSON) that drive decisions.

## Hard rules for large files

- Do not `cat` or print whole workbook-derived outputs to the console.
- Do not build full-cell inventories unless truly required; if required, write to
  file and print a short summary.
- Use read-only iteration (`load_workbook(..., read_only=True)`) to bound memory.
- Separate direct facts from derived claims; never present a derived claim without
  the calculation path.
- For timeline-sensitive metrics, always include explicit period labels and
  source location.

## Inspecting workbook structure

Scope by size: full inventory is fine for small and medium workbooks; for large
ones, profile and sample first, then inventory only relevant sheets and ranges.
When a full inventory is needed, never truncate cell values; write to JSON and
print only a summary.

```python
from openpyxl import load_workbook
import json

wb = load_workbook('template.xlsx')
inventory = {}
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    cells = []
    for row in sheet.iter_rows(min_row=sheet.min_row, max_row=sheet.max_row,
                               min_col=sheet.min_column, max_col=sheet.max_column):
        for cell in row:
            if cell.value is not None:
                cells.append({
                    'ref': cell.coordinate,
                    'value': cell.value if cell.data_type != 'f' else None,
                    'formula': cell.value if cell.data_type == 'f' else None,
                    'type': cell.data_type,
                })
    inventory[sheet_name] = {'dimensions': sheet.dimensions, 'cell_count': len(cells), 'cells': cells}

with open('workbook_inventory.json', 'w') as f:
    json.dump(inventory, f, indent=2, default=str)

for name, data in inventory.items():
    print(f"{name}: {data['cell_count']} cells")        # summary only
```

Do NOT flood the console by printing every cell with truncated values
(`str(cell.value)[:100]`); that loses data and tells you nothing.
