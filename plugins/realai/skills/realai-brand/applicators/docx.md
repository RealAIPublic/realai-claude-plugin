# DOCX Applicator

> Ported from the original `realai-docx-formatter` agent. Reads visual tokens from `tokens.md`. Returns a re-skinned `.docx` whose text runs are byte-identical to the input. Verification spine is non-negotiable.

## Units (OOXML)

OOXML uses idiosyncratic units. Convert from token values (points) using these rules:

- Run size `w:sz` = half-points (`pt = sz / 2`).
- Paragraph `w:spacing` before/after = twips (`20 twips = 1 pt`).
- Border `w:sz` = eighths of a point (`pt = sz / 8`).
- Cell margins = twips.
- Character tracking `w:spacing` = twentieths of a point.
- Colors in OOXML are bare 6-hex (no leading `#`).

### Pre-computed conversions for the RealAI type scale

| Element | Point | `w:sz` (half-pt) |
|---|---|---|
| Document title | 28 | 56 |
| H1 | 20 | 40 |
| H2 (section) | 15 | 30 |
| H3 | 12 | 24 |
| Eyebrow / kicker | 9 | 18 |
| Body | 11 | 22 |
| Body small | 10 | 20 |
| Caption | 9 | 18 |
| Disclaimer | 9 | 18 |
| Table cell | 10 | 20 |
| Table header | 9 | 18 |

### Pre-computed conversions for paragraph rhythm

| Element | Before (twips) | After (twips) | Line (`w:line`, lineRule) |
|---|---|---|---|
| Title | 0 | 120 | single |
| H1 | 320 | 120 | single |
| H2 | 280 | 80 | single |
| H3 | 200 | 60 | single |
| Eyebrow | 0 | 40 | single |
| Body / bullets | 0 | 140 | 276 auto (1.15) |
| Disclaimer | 200 | 0 | single |

### Pre-computed border weights

| Border | Point | `w:sz` (eighths) |
|---|---|---|
| Table hairline (all + inside) | 0.5 | 4 |
| H2 section rule | 0.75 | 6 |
| Table header bottom rule | 1.5 | 12 |

### Page size and margins (twips)

- Letter: 12240 × 15840
- Margins: top/bottom 1440, left/right 1620

## What to apply (style layer only)

1. **Redefine document styles** (Normal, Title, Heading 1–3, List, table styles) to the token values.
2. **Strip ALL direct formatting on runs** unconditionally — font family, explicit color, size, highlight — regardless of what colors or fonts are present in the source document. Treat the source as having no brand colors. Apply the RealAI palette from scratch using `tokens.md`. KEEP bold / italic / underline (semantic intent only).
3. **Promote section titles to real heading styles** (see detection rule in `tokens.md`). Replace any colored underline with the orange H2 rule.
4. **Remove manual page breaks**; enable widow/orphan control; set `cantSplit` on table rows.
5. **Apply table and chart rules** from `tokens.md`. Recolor native charts' series/text/gridlines. If a chart is an embedded image you cannot recolor it — leave it and flag it.

## What never to touch

Per the universal rule in `SKILL.md`: text runs (words, numbers, $/%/x, dates), table cell values, chart underlying data. Bold/italic/underline preserved. Casing is presentation via styling, never by editing characters.

## Verify before returning (REQUIRED)

Extract every text run from the input and from the formatted output, in order, ignoring whitespace-only runs. They MUST be identical. If they differ, the formatting altered content — **discard the output and report it**. Never return a document whose text changed.

## Implementation entry point

Run via `scripts/apply_docx_brand.py`. The script:

1. Loads the input `.docx`.
2. Snapshots every text run (ordered list of strings, whitespace-only runs filtered out).
3. Applies the style layer per the rules above.
4. Re-snapshots text runs.
5. Asserts byte-identity of the two snapshots.
6. On mismatch, deletes the work product and returns an error.
7. On success, writes the re-skinned `.docx` and returns the path.
