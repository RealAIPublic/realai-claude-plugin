"""Phase 4 — Emit a personalized realai-pro-forma skill as a .plugin zip.

Takes the cleaned template + manifest produced by Phases 1–3 and packages a
standalone .plugin zip that the customer can install via their Cowork plugin
marketplace. The zip is a clone of realai-pro-forma with the customer's
artifacts bundled and the SKILL.md description specialized to their deal type.

Usage:
    python emit_personalized_skill.py \\
        --cleaned /path/to/{name}_cleaned.xlsx \\
        --manifest /path/to/{name}_manifest.md \\
        --org-name "AcmeRealEstate" \\
        --deal-type acquisition \\
        --version 1.0.0 \\
        --out /path/to/outputs/

Produces: /path/to/outputs/{org-slug}-pro-forma_v{version}.plugin

Versioned re-emission: call with the same --org-name and a bumped --version.
The zip is self-contained; old populated workbooks built against the prior
manifest version still work because the manifest is bundled inside that
version's emitted skill.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# Path to the canonical realai-pro-forma skill we're cloning. When this script
# runs inside an installed plugin, this resolves relative to the plugin root.
DEFAULT_TEMPLATE_SKILL = Path(__file__).resolve().parents[3] / "realai-pro-forma"


DEAL_TYPE_DESCRIPTIONS = {
    "acquisition": (
        "Use this skill any time the user asks you to underwrite a multifamily "
        "or commercial real estate acquisition for {org_name}. Activate on "
        "phrasings like 'underwrite this deal', 'run the proforma on', 'screen "
        "this acquisition'. The bundled template and manifest are tailored to "
        "{org_name}'s standard acquisition model."
    ),
    "value_add": (
        "Use this skill any time the user asks you to underwrite a value-add "
        "multifamily deal for {org_name}. Activate on phrasings like 'value-add "
        "proforma', 'run the renovation underwriting', 'underwrite this "
        "reposition'. The bundled template and manifest are tailored to "
        "{org_name}'s value-add model."
    ),
    "development": (
        "Use this skill any time the user asks you to underwrite a ground-up "
        "development for {org_name}. Activate on phrasings like 'development "
        "feasibility', 'ground-up underwriting', 'run the dev proforma'. The "
        "bundled template and manifest are tailored to {org_name}'s development "
        "model."
    ),
    "conversion": (
        "Use this skill any time the user asks you to underwrite a building "
        "conversion (office-to-MF, etc.) for {org_name}. The bundled template "
        "and manifest are tailored to {org_name}'s adaptive reuse model."
    ),
    "waterfall": (
        "Use this skill any time the user needs to run {org_name}'s standard "
        "waterfall pro forma. Activate on phrasings like 'run the waterfall', "
        "'investor distributions', 'promote calculations'. The bundled template "
        "and manifest are tailored to {org_name}'s waterfall model."
    ),
    "mixed_use": (
        "Use this skill any time the user asks you to underwrite a mixed-use "
        "deal for {org_name}. The bundled template and manifest are tailored to "
        "{org_name}'s mixed-use model."
    ),
    "generic": (
        "Use this skill any time the user asks {org_name} to underwrite, run a "
        "pro forma on, or build an investment screen for a real estate "
        "acquisition or value-add deal. The bundled template and manifest are "
        "tailored to {org_name}'s standard underwriting model."
    ),
}


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build_specialized_skill_md(template_skill_md: str, org_name: str, deal_type: str) -> str:
    """Rewrite SKILL.md frontmatter `description` to specialize for org + deal type."""
    desc_template = DEAL_TYPE_DESCRIPTIONS.get(deal_type, DEAL_TYPE_DESCRIPTIONS["generic"])
    new_desc = desc_template.format(org_name=org_name)

    # Replace name + description in YAML frontmatter only.
    lines = template_skill_md.splitlines(keepends=True)
    in_frontmatter = False
    out = []
    frontmatter_seen = 0
    for line in lines:
        if line.strip() == "---":
            frontmatter_seen += 1
            in_frontmatter = frontmatter_seen == 1
            out.append(line)
            continue
        if in_frontmatter and line.startswith("name:"):
            out.append(f"name: {slugify(org_name)}-pro-forma\n")
            continue
        if in_frontmatter and line.startswith("description:"):
            out.append(f"description: \"{new_desc}\"\n")
            continue
        out.append(line)
    return "".join(out)


def build_plugin_json(org_name: str, deal_type: str, version: str, source_template: str) -> dict:
    return {
        "name": f"{slugify(org_name)}-pro-forma",
        "version": version,
        "description": (
            f"Personalized pro forma skill for {org_name} ({deal_type} model). "
            f"Emitted by realai-prepare-template from source template '{source_template}'."
        ),
        "author": {"name": org_name},
        "license": "Proprietary",
        "metadata": {
            "source_template": source_template,
            "deal_type": deal_type,
            "prepared_at": datetime.datetime.utcnow().isoformat() + "Z",
            "prepared_by": "realai-prepare-template",
        },
    }


def build_changelog(org_name: str, deal_type: str, version: str, source_template: str, manifest_status: str) -> str:
    return (
        f"# Changelog — {org_name} Pro Forma\n\n"
        f"## v{version} — {datetime.date.today().isoformat()}\n\n"
        f"- Initial emission from `realai-prepare-template`.\n"
        f"- Source template: `{source_template}`\n"
        f"- Deal type: `{deal_type}`\n"
        f"- Manifest status: `{manifest_status}`\n"
        f"- Bundled artifacts: `assets/{slugify(org_name)}_cleaned.xlsx`, `assets/manifest.md`\n"
    )


def emit(cleaned: Path, manifest: Path, org_name: str, deal_type: str, version: str,
         out_dir: Path, template_skill_dir: Path = DEFAULT_TEMPLATE_SKILL,
         manifest_status: str = "ready") -> Path:
    """Build the .plugin zip and return its path."""
    if not cleaned.exists():
        raise FileNotFoundError(f"Cleaned template not found: {cleaned}")
    if not manifest.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest}")
    if not template_skill_dir.exists():
        raise FileNotFoundError(f"Template skill not found at {template_skill_dir}")

    slug = slugify(org_name)
    skill_name = f"{slug}-pro-forma"
    plugin_name = f"{skill_name}_v{version}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        plugin_root = tmp_path / plugin_name
        skill_root = plugin_root / "skills" / skill_name
        skill_root.mkdir(parents=True)

        # 1. Clone realai-pro-forma into the skill root, except SKILL.md (specialized below)
        for item in template_skill_dir.iterdir():
            if item.name == "SKILL.md":
                continue
            if item.is_dir():
                shutil.copytree(item, skill_root / item.name)
            else:
                shutil.copy2(item, skill_root / item.name)

        # 2. Replace bundled template + manifest assets
        assets_dir = skill_root / "assets"
        assets_dir.mkdir(exist_ok=True)
        # Wipe any default RealAI assets, then drop the customer's in.
        for old in assets_dir.iterdir():
            if old.is_file():
                old.unlink()
        shutil.copy2(cleaned, assets_dir / f"{slug}_cleaned.xlsx")
        shutil.copy2(manifest, assets_dir / "manifest.md")

        # 3. Specialize SKILL.md
        template_md = (template_skill_dir / "SKILL.md").read_text(encoding="utf-8")
        specialized_md = build_specialized_skill_md(template_md, org_name, deal_type)
        (skill_root / "SKILL.md").write_text(specialized_md, encoding="utf-8")

        # 4. Plugin manifest
        plugin_meta_dir = plugin_root / ".claude-plugin"
        plugin_meta_dir.mkdir()
        plugin_json = build_plugin_json(org_name, deal_type, version, str(cleaned.name))
        (plugin_meta_dir / "plugin.json").write_text(json.dumps(plugin_json, indent=2), encoding="utf-8")

        # 5. CHANGELOG
        changelog = build_changelog(org_name, deal_type, version, str(cleaned.name), manifest_status)
        (plugin_root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

        # 6. Zip into the output dir
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / f"{plugin_name}.plugin"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in plugin_root.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(plugin_root.parent))
        return zip_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Emit a personalized realai-pro-forma .plugin zip.")
    parser.add_argument("--cleaned", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--org-name", required=True)
    parser.add_argument("--deal-type", required=True,
                        choices=sorted(DEAL_TYPE_DESCRIPTIONS.keys()))
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--manifest-status", default="ready",
                        choices=["ready", "ready_with_limitations"])
    parser.add_argument("--template-skill", type=Path, default=DEFAULT_TEMPLATE_SKILL)
    args = parser.parse_args(argv)

    try:
        zip_path = emit(
            cleaned=args.cleaned,
            manifest=args.manifest,
            org_name=args.org_name,
            deal_type=args.deal_type,
            version=args.version,
            out_dir=args.out,
            template_skill_dir=args.template_skill,
            manifest_status=args.manifest_status,
        )
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    print(f"OK: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
