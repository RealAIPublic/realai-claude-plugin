# XLSX Applicator — STUB

> **STATUS: STUB — DO NOT MUTATE FILES.** This applicator is documented but not implemented. Until implementation lands, calls into this applicator must be no-ops that return the input file unchanged with a `not_implemented` flag. The contract below defines what the future implementation must do and — critically — what it must NEVER do.

## Why a separate applicator?

Spreadsheets carry math. The docx applicator can strip and re-apply visual styles freely because text and numbers are inert payload. In a workbook, the same byte you might want to recolor can be a precedent inside a recalc chain, a named range that drives validation, a chart's source reference, or a pivot table's source. A formatter that mutates these is not a formatter — it's a model corrupter.

This applicator's contract is therefore much narrower than the docx applicator's.

## Hard rules (MUST NEVER violate)

The xlsx applicator MUST NEVER:

- Touch formulas. Read-only access to formula text and result; zero write access.
- Touch named ranges. Read-only inspection; no rename, redefine, add, or delete.
- Touch data validation rules. No add, modify, or delete.
- Touch chart source references. Visual recolor of series is allowed only if the source range itself is untouched.
- Touch the recalc chain. Do not trigger a recalc; do not change cells flagged as `dirty`.
- Touch defined tables (`<table>` in xlsx XML). No header rename, no column add/remove, no totals-row toggle.
- Touch pivot tables, pivot cache, or pivot source ranges.
- Add or remove sheets, hide or unhide sheets, change sheet protection.
- Touch external links or query connections.
- Touch conditional formatting rules.

## What the applicator MAY do (presentation layer only)

- Restyle fills (cell background color), within the token palette.
- Restyle fonts (family, size, color, bold/italic — semantic), within tokens.
- Restyle borders (line weight, color), within tokens.
- Restyle number formats — BUT ONLY if the existing format is purely visual (`#,##0`, `0.00%`, etc.). If the existing format encodes business logic (`[Red]-#,##0;[Blue]#,##0`), leave it alone.
- Restyle alignment (horizontal, vertical), only where this doesn't disrupt structured tables.
- Restyle row height / column width within a tolerance (do not collapse or hide).

## Token consumption

Read `tokens.md`. Use the same palette, font stack, type scale, and table styling rules. The mapping from tokens → xlsx style XML is the implementation's job; the visual output should be indistinguishable from a `.docx` version of the same content.

### Number format coordination

When the docx applicator and the xlsx applicator both produce deliverables for the same analysis, number formats must agree. The xlsx applicator uses Excel format codes; the docx applicator uses text directly. The implementation must include a token-to-format-code mapping table so the two stay aligned.

## Verification spine

The universal verification rule applies. After styling, the applicator must:

1. Snapshot every cell's value (not its style) before and after, ordered by sheet and address.
2. Snapshot every formula's text before and after.
3. Snapshot every named range's reference and scope.
4. Snapshot every defined-table column.
5. Snapshot every chart's data references.

If ANY of these differs between input and output, **discard the output and report**. The user can re-style by hand faster than they can debug a quietly-corrupted model.

## Implementation entry point (future)

`scripts/apply_xlsx_brand.py` — not present this run. When implemented, it must follow the same lifecycle as the docx applicator: load → snapshot → apply style layer → re-snapshot → assert byte-identity on values/formulas/names/tables/chart-refs → write or discard.

## Until implementation lands

Calls from upstream skills (e.g., `realai-pro-forma`, `realai-underwriting`) into this applicator should:

1. Detect the `not_implemented` status.
2. Return the input workbook unchanged.
3. Flag in the receipt that visual branding was skipped because the xlsx applicator is stubbed.

This avoids silently degrading the math authority of populated workbooks.
