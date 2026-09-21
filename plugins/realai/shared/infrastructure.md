# Using the application skills in Claude

The six directories below are unchanged imports of the application skills, including
SKILL.md, references, and scripts. Read the relevant imported skill when the task needs
its method. These are
shared dependencies of the four domain skills, not additional automatic entrypoints.

This file is the Claude integration layer. It supplies host paths, tool equivalents, and
the caller's conversational scope without editing the application's methods or code.

## Choose the dependency

| Task | Imported skill |
|---|---|
| Select and interpret rental comparables | `${CLAUDE_PLUGIN_ROOT}/shared/rental-comps/SKILL.md` |
| Select and interpret sales comparables | `${CLAUDE_PLUGIN_ROOT}/shared/sales-comps/SKILL.md` |
| Read, audit, build, edit, or populate a workbook | `${CLAUDE_PLUGIN_ROOT}/engines/xlsx/SKILL.md` |
| Remove prior-deal data from an existing reusable workbook | `${CLAUDE_PLUGIN_ROOT}/engines/clean-a-template/SKILL.md` |
| Compute forecast scenarios or historical capital-market bands | `${CLAUDE_PLUGIN_ROOT}/engines/forecasting/SKILL.md` |
| Compute supported multifamily statements, valuation, or returns | `${CLAUDE_PLUGIN_ROOT}/engines/mf-operating-statement/SKILL.md` |

Both underwriting and multifamily use the same comp skills. Do not copy their selection
rules into a domain reference. `clean-a-template` cleans; it neither populates a model nor
creates a field mapping or manifest. Use xlsx for ordinary workbook work. The old templates
filler and renamed workbooks bundle are retired from the active plugin.

## Resolve paths without modifying the imported files

Application command examples assume an application workspace containing `skills/<name>`.
Replace that path in the command you execute with the absolute directory in the table
above (without its `/SKILL.md` suffix). Resolve imported relative references against their
own skill directory. Do not assume the current directory is the application repository,
create a second copy of a script, or reconstruct one from documentation.

`${CLAUDE_PLUGIN_ROOT}` in this guide is host substitution in plugin content. Use its
resolved absolute path in executed commands; do not assume a plain shell exports it.
Keep generated payloads, working copies, and outputs in the task's writable workspace,
not in the installed plugin. Run imported scripts with an available Python runtime and
their declared dependencies; do not silently replace a script if a dependency is absent.

Full template cleanup uses xlsx OOXML helpers as well as openpyxl; those helpers need
`defusedxml` and `lxml`. Recalculation requires an available LibreOffice `soffice` and
a writable profile directory. Check the actual host before claiming a workbook is ready.

For `clean-a-template`, set `REALAI_XLSX_SKILL_ROOT` to the resolved absolute
`${CLAUDE_PLUGIN_ROOT}/engines/xlsx` path for the cleanup process. This is the upstream
supported dependency override. It connects cleanup to the one canonical xlsx helper set;
do not rely on the application's `skills/xlsx` filesystem fallback or copy helpers.

## Map host operations

| Application assumption | Claude equivalent |
|---|---|
| Sandbox execution and file-write tools | The host's available code/file tools, using the exact bundled script |
| Datamart lookup | The authenticated MCP and `shared/data-retrieval/data-access.md` |
| Library save/load/present | Available host file access and artifact delivery; link the actual delivered file |
| Application file-ID/cell citations | Host-supported artifact citations; otherwise identify workbook, sheet, and cell beside the finding |

Never invent application tool names, library file IDs, citation registration, or delivery
success. Preserve the source's purpose: read back the recalculated value, make the exact
workbook and cell identifiable, and deliver the artifact. If the host cannot render a
cell link, give the actual file link with a plain sheet/cell locator. An unavailable
recalculation or package-validation step limits readiness exactly as the source specifies;
a host adapter is not permission to skip its integrity gates.

## Caller scope and presentation

The domain question decides which infrastructure to invoke. An observed trend does not
become a numerical forecast because a forecasting skill exists. A scalar financial
question does not automatically request a workbook. The application's automatic workbook
trigger and app-specific response ceremony do not expand the user's requested deliverable
in Claude; follow `output-conventions.md`. When a workbook is requested, apply the imported
xlsx formula, reconciliation, and delivery gates in full.

Keep all engine confidence and diagnostic fields in saved results. Inspect every flag,
but present only requested diagnostics and material limitations in clear language near
the affected conclusion. Do not weaken a forecast guard, omit a consequential gap, or
alter returned calculations. This caller-level presentation rule replaces the app's
verbatim flag-dump requirement without changing the imported forecasting skill.

Treat comp results as the retrieved candidate pool, not an exhaustive geography-wide
ranking. Follow the upstream comp selection workflow, actual MCP schema, and honest
coverage reporting. Only make distance, recency, or completeness claims the retrieval
supports. A field-specific upstream definition of NULL is distinct from assuming that
all NULLs mean zero, suppression, or absence.

For template cleanup, preserve the source's readiness statuses, required evidence,
explicit decision boundaries, and leak/integrity gates. Do not use the conversational
default to waive them. Unsupported non-MF cash-flow structures must not be forced through
multifamily recipes; use the requested workbook's actual structure or state the specific
unsupported output while continuing with supported evidence.
