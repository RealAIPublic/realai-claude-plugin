---
name: mf-operating-statement
description: "Use this skill to build a multifamily operating statement (waterfall: GPR → Vacancy → Other Income → OpEx → NOI) and, on request, project it forward and derive valuation or returns — direct cap, DCF/unlevered IRR, levered IRR/equity multiple/cash-on-cash, or development yield-on-cost. Trigger whenever a deliverable needs an NOI build, a forward projection of multifamily cash flows, or any of those valuation/returns outputs — underwriting, screening, valuation, refi, development, or operations — even when the user does not say 'operating statement' or 'income statement.' The arithmetic runs in a bundled sandbox script; this skill owns the routing, stabilization judgment, and validation around it."
license: Proprietary
---

# Multifamily Operating Statement & Projection

## Contents

- Workflow
- Running the script
- Interpreting output
- Key judgment the skill owns (script enforces the mechanics)
- Reference files

Pure-compute workflow: resolve what to build, hand structured inputs to the bundled
script, interpret what it returns. All arithmetic runs in `scripts/operating.py` — never
compute NOI, IRR, amortization, DCF, or yields in prose. This matches the platform rule that
no financial figure is computed in your head or in prose: figures run in the sandbox, model
math runs in a workbook, and a bundled script like this one is the calculation authority for
the figures it owns.

This skill does **not** fetch data, parse documents, or pull comps. The caller supplies
every input. If inputs are missing, resolve them upstream first (query the datamart, read
the OM/T12, prompt the user) — then invoke this skill.

## Workflow

1. **Pick the mode** from the user's intent (see table). Default to `base_year_only` when
   they only want the statement.
2. **Assemble the request JSON** — see `references/schema.md` for the full request/response
   contract and the per-mode field-requirement table. Map reported figures verbatim; do not
   pre-compute derived lines.
3. **Run the script** in the sandbox (below). It resolves the scenario, builds the base year,
   determines stabilization status, runs projection/valuation/returns as the mode requires,
   and self-validates.
4. **Read `status`** and act on it (see Interpreting output).
5. **Present the result** as a waterfall table (+ projection/returns tables as relevant),
   leading with the decision-relevant takeaway. Narrative framing is owned by the parent
   analysis, not this skill.

   An operating statement is workbook-shaped by construction — an NOI build of linked lines
   meets the platform's workbook trigger — so when this skill's output is the body of a deliverable
   reaching the user, load the `xlsx` skill and build the statement as a live workbook: that table is the read and
   the workbook is the deliverable. This script owns the arithmetic; it does not replace the
   workbook. The boundary: land what the script returns as labeled input cells — the reported
   figures, the resolved assumptions, and any per-period values whose logic the script owns
   (a stabilization ramp, an engine-fed rent series), which land period by period, never as
   growth-rate formulas that re-implement the ramp. The waterfall's derived lines (EGI, NOI,
   the mode's value and returns lines) are formulas referencing those inputs, so the user can
   move an assumption and watch NOI move. Do not paste the computed waterfall in as literals:
   a projection or returns sheet with no formulas is a dead model. After the `xlsx` skill's
   gate, tie out: the workbook's NOI and mode outputs must equal what the script returned — a
   mismatch means the formulas mis-implement the resolution; fix the formulas, never the
   script's numbers.

| Mode | Produces |
|---|---|
| `base_year_only` | Base-year statement, then stop |
| `projection` | Base year + N-year forward waterfall |
| `direct_cap` | Direct-cap value from stabilized NOI |
| `dcf` | NPV + unlevered IRR from projected cash flows |
| `levered_returns` | Levered IRR, equity multiple, cash-on-cash |
| `yield_on_cost` | Untrended & trended YoC for development |

Any mode other than `base_year_only` runs the base year internally first — do not invoke it
separately. Extra inputs beyond what the mode needs are ignored, not acted on.

Two gotchas worth knowing before assembling the request:
- `dcf`'s `unlevered_irr` only computes when `valuation_inputs.purchase_price` is supplied
  (it's the entry outlay the rate solves against) — omit it and `npv`/`value_per_unit` still
  come back, but `unlevered_irr` is `null`, not an error.
- A `value-add` stabilization status (inferred, overridden, or defaulted) requires
  `property_context.units`, `property_context.in_place_rent`, and
  `projection_inputs.post_renovation_rent` for any mode beyond `base_year_only` — missing any
  of them is a blocking error, since the rent ramp can't be defaulted.

## Running the script

Write the request to a file and pipe it in; read structured JSON back.

```bash
sandbox_write /tmp/req.json '<the request JSON>'
python3 skills/mf-operating-statement/scripts/operating.py < /tmp/req.json > /tmp/out.json
cat /tmp/out.json
```

The script is stateless — every call must carry all context. It makes no network or tool
calls of its own.

## Interpreting output

- **`status: "ok"`** — all requested computations succeeded. `validation.data_quality_flags`
  may still be populated; those are advisory. Surface material flags to the user (e.g. OpEx
  ratio outside 35–55%, an unusual vacancy rate) rather than burying them.
- **`status: "unknown"`** — the base year built, but stabilization status could not be
  resolved, so projection did not run. Read `unknown_resolution`, resolve status (usually by
  pulling `market_rent` or asking the user), then re-invoke with
  `property_context.stabilization_status_override` set. Present the partial base-year
  statement meanwhile.
- **`status: "error"`** — terminal. Read `validation.blocking_failures`, fix the inputs, and
  re-invoke. No statement is returned. Do not paper over an error by computing by hand.

## Key judgment the skill owns (script enforces the mechanics)

- **Scenario resolution** — which base-year recipe applies, driven by which
  `mf_property_financials` fields are populated. See `references/schema.md`.
- **Stabilization status** — override → inference → default. This gates projection behavior
  (stabilized / lease-up / value-add ramps). Full logic in `references/methodology.md`.
- **Validation** — blocking failures vs. advisory flags. Full list in
  `references/methodology.md`.

Read `references/methodology.md` when you need the exact recipes, growth/ramp rules, mode
math, or validation checks — it is the faithful expansion of the compute contract.

## Reference files

- `references/schema.md` — request & response JSON, field requirements by mode, scenario
  triggers.
- `references/methodology.md` — base-year recipes, stabilization logic, projection rules,
  mode-specific calculations, validation.
