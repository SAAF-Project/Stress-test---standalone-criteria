"""
Write per-project JSON reports and the human-readable summary.md.
"""
import json
from pathlib import Path

from .verdict import ProjectReport

_VERDICT_ICON = {"yes": "✅", "partial": "⚠️", "no": "❌"}


def write_project_report(report: ProjectReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{report.project}.json"
    data = {
        "project": report.project,
        "standalone_ready": report.standalone_ready,
        "model_access": report.model_access,
        "blockers": report.blockers,
        "cloud_only_features": report.cloud_only_features,
        "notes": report.notes,
    }
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


def write_summary(reports: list[ProjectReport], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = sorted(reports, key=lambda r: r.project)
    lines = [
        "# Standalone Readiness Summary\n",
        "| Project | Verdict | Top Blocker |",
        "| :------ | :-----: | :---------- |",
    ]
    for r in rows:
        icon = _VERDICT_ICON.get(r.standalone_ready, "?")
        top = r.blockers[0]["type"] if r.blockers else "—"
        lines.append(f"| {r.project} | {icon} `{r.standalone_ready}` | {top} |")

    out = output_dir / "summary.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
