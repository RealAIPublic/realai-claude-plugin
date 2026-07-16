# RealAI Brand Tokens

Format-neutral design tokens. All applicators (`docx.md`, `xlsx.md`, `pptx.md`) consume these values and translate them into the target format's unit system. Do not duplicate values into applicator files; reference this document.

## Colors

| Role | Hex (no leading `#`) | Used for |
|---|---|---|
| Content / primary | `151513` | Body text, headings, titles |
| Content / tertiary | `6B6A65` | Labels, captions, disclaimers, axis text |
| Accent (orange) | `F4633A` | The single accent: section rules, key figure, chart series 1, links |
| Canvas white | `FFFFFF` | Page background |
| Greige | `FAF9F6` | Table header fill, soft section fills |
| Blackish | `22262A` | Dark header band (when a dark band is used) |
| Border / hairline | `E4E3DF` | Table borders, dividers, gridlines |
| Slate | `5B6B7A` | Chart series 2, informational |
| Gold | `B8923B` | Chart series 3, premium-tier accent |
| Status red | `C0392B` | Status only — never decorative |
| Status yellow | `C9A227` | Status only — never decorative |

### Source-color remapping

When the input deliverable already has color, applicators must remap source colors onto the RealAI palette:

- Navy / dark band → `22262A` (or `FAF9F6` if light)
- Corporate blue accents/headings → text `151513` with an orange `F4633A` rule
- Body gray (e.g. `333333`) → `151513`
- Label grays → `6B6A65`

## Fonts

| Role | Primary | Fallback |
|---|---|---|
| Document title, large stat numbers | Ivar Display | Georgia |
| H1–H3, pull quotes | Ivar Headline | Georgia |
| Body, labels, tables, captions, eyebrows | Source Sans 3 (alt: Source Sans Pro) | Calibri |

Fonts: the file declares Ivar + Source Sans 3; viewers without them substitute (still clean). Install the licensed fonts for the exact look.

## Type sizes

Sizes in points. Applicator-specific unit conversions (e.g., OOXML half-points for docx) are documented inside each applicator file.

| Element | Point size |
|---|---|
| Document title | 28 |
| H1 | 20 |
| H2 (section) | 15 |
| H3 | 12 |
| Eyebrow / kicker | 9 |
| Body | 11 |
| Body small | 10 |
| Caption | 9 |
| Disclaimer | 9 |
| Table cell | 10 |
| Table header | 9 |

**Compact one-pagers:** render section labels at 9–10 pt UPPERCASE instead of full 15 pt H2 to preserve density.

## Paragraph rhythm

Spacing values in points. Conversion to format-specific units (twips for docx) is the applicator's responsibility.

| Element | Before (pt) | After (pt) | Line |
|---|---|---|---|
| Title | 0 | 6 | single |
| H1 | 16 | 6 | single |
| H2 | 14 | 4 | single |
| H3 | 10 | 3 | single |
| Eyebrow | 0 | 2 | single |
| Body / bullets | 0 | 7 | 1.15 |
| Disclaimer | 10 | 0 | single |

**Eyebrow rules:** UPPERCASE, letter-spacing +1.1 pt, color `6B6A65`, bold.
**H2 section rule:** bottom border, orange `F4633A`, 0.75 pt.
**Heading weight:** comes from the serif face + size, not bold. Align left.

## Tables

| Property | Value |
|---|---|
| Borders (all + inside) | 0.5 pt hairline, color `E4E3DF` |
| Header fill | `FAF9F6`; text `151513`, bold |
| Header bottom rule | 1.5 pt, color `F4633A` |
| Body cell text | `151513` |
| Zebra (optional) | alternate `F4F3EF` / white |
| Cell padding | 4 pt vertical, 6 pt horizontal |
| Numeric columns | right-aligned; tabular figures |
| Rows | cantSplit; header row repeats |

## Charts

- **Series color order:** `F4633A`, `5B6B7A`, `B8923B`, `C7D0D8`, `6B6A65`.
- **Gridlines:** `E4E3DF` (~0.8 px); axis/label text `6B6A65`; title and data labels `151513`.
- No top/right spines; bottom spine `E4E3DF`; white/transparent background; no gradients, no 3D.

## Page (docx)

- US Letter, 8.5 × 11 in.
- Margins: top/bottom 1.0 in, left/right 1.125 in.

## Casing, numbers, voice

- Sentence case for headings/titles/labels; Title Case ONLY for product/fund names.
- Numbers always with $/%/x and thousands separators; +/− prefixes for performance; right-align stacked numbers.
- Disclaimers understated, tertiary color.
- No emoji; no exclamation points except transactional confirmations.

## Section-title detection rule (applies to docx today; carries to pptx when implemented)

Treat a paragraph as a section title to promote when ALL hold:

- It is short (≤ ~8 words).
- It sits on its own line.
- It is visually distinguished from body (bold, or a non-body color, or ALL CAPS, or already a heading style).

Numbered leads like `"1. ECONOMY..."` and all-caps labels like `"KEY METRICS AT A GLANCE"` qualify → H2. Short bold labels ending in a colon (e.g. `"Strengths:"`) → H3 (no rule). Do not change the text; only the style.
