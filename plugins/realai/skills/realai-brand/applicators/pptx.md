# PPTX Applicator — STUB

> **STATUS: STUB — DO NOT MUTATE FILES.** This applicator is documented but not implemented. Until implementation lands, calls into this applicator must be no-ops that return the input file unchanged with a `not_implemented` flag.

## Why a separate applicator?

Slide decks are structured for layout inheritance — a placeholder on a slide pulls geometry, type, and color from a slide layout, which inherits from a slide master, which inherits from a theme. A naive recolor that writes color values onto individual shapes wins the immediate slide but breaks the moment a user adds a new slide from the same layout. The applicator must respect the theme → master → layout → slide cascade.

PPTX uses DrawingML throughout, with EMUs (English Metric Units) as the underlying unit (`914400 EMU = 1 inch`).

## Hard rules (MUST NEVER violate)

The pptx applicator MUST NEVER:

- Touch chart source data (`<c:numCache>`, `<c:strCache>`, or external data refs). Visual recolor of series is allowed only if data is untouched.
- Touch placeholder identity (`idx`, `type`) — these drive layout inheritance.
- Change slide order or add/remove slides.
- Touch animations or transitions.
- Touch speaker notes text (notes pages are deliverable content).
- Change embedded media, OLE objects, or linked spreadsheets.
- Touch text frames' textual content — only their style.

## What the applicator MAY do

- Restyle the theme (`theme1.xml`) — `<a:clrScheme>`, `<a:fontScheme>`, `<a:fmtScheme>` — to the RealAI palette/fonts/effects.
- Restyle slide masters — header band fill, color overlay, default text style.
- Restyle slide layouts — placeholder positions, fill, default fonts.
- Restyle individual shapes' fills, line weights, font colors — only when the shape carries direct formatting overriding inherited theme values, AND the new value matches the theme equivalent.
- Recolor chart series, gridlines, axis text — via the chart's style XML, not its data.
- Replace fonts that don't match the token list with the appropriate fallback.

## Token consumption

Read `tokens.md`. Map:

- Token colors → `<a:clrScheme>` slots (`dk1`, `lt1`, `accent1` = `F4633A`, etc.).
- Token fonts → `<a:fontScheme>` major (Ivar) / minor (Source Sans 3).
- Token type sizes → slide master placeholder default styles.
- Token chart series order → chart style XML `<c:varyColors val="0"/>` plus series fills in order.

## Verification spine

The universal verification rule applies. After styling, the applicator must:

1. Snapshot every text frame's text content (ordered by slide → shape → paragraph → run).
2. Snapshot every chart's data references.
3. Snapshot every embedded media path.
4. Snapshot every placeholder's `idx` and `type`.
5. Snapshot every slide's layout reference.

If ANY of these differs between input and output, **discard the output and report**.

## Implementation entry point (future)

`scripts/apply_pptx_brand.py` — not present this run. Follow the same lifecycle as the docx applicator: load → snapshot → apply theme + master + layout edits → re-snapshot → assert byte-identity on text / chart data / media / placeholders / layout refs → write or discard.

## Until implementation lands

Calls from upstream skills into this applicator should:

1. Detect the `not_implemented` status.
2. Return the input deck unchanged.
3. Flag in the receipt that visual branding was skipped because the pptx applicator is stubbed.
