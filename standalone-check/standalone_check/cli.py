"""
standalone-check CLI entry point.

Usage:
    standalone-check /path/to/monorepo [options]
    standalone-check /path/to/monorepo --no-llm
    standalone-check /path/to/monorepo -p agent-foo -p agent-bar
"""
import sys
from pathlib import Path

import click

from .llm_pass import run_llm_pass
from .reporter import write_project_report, write_summary
from .scanner.config_files import scan_config_files
from .scanner.files import source_files, read_source, project_files
from .scanner.python_ast import scan_python_project
from .scanner.ripgrep import scan_js_ts_project
from .verdict import compute_verdict

_VERDICT_ICON = {"yes": "✅", "partial": "⚠️", "no": "❌", "not_assessed": "❔"}

def _discover_projects(repo_root: Path) -> list[Path]:
    """Return projects to scan.

    Monorepo: returns immediate subdirectories that contain source code.
    Single-project repo: if no subdirectories qualify, falls back to root.
    """
    paths = source_files(repo_root)
    # Root-level source means this is one project, including its nested packages.
    # Previously a sibling folder caused root-level blockers to disappear.
    root_files = [p for p in project_files(repo_root) if p.parent == repo_root]
    root_config = any(
        p.name in {"pyproject.toml", "setup.cfg", "package.json"}
        or p.match("requirements*.txt") or p.name.startswith(".env")
        or p.suffix in {".yaml", ".yml"} for p in root_files
    )
    if paths and (root_config or any(p.parent == repo_root for p in paths)):
        return [repo_root]
    names = sorted({p.relative_to(repo_root).parts[0] for p in paths})
    return [repo_root / name for name in names]


def _collect_snippets(proj_dir: Path, max_files: int = 8, max_chars: int = 500) -> list[str]:
    paths = [p for p in source_files(proj_dir) if p.suffix == ".py"][:max_files]
    return [read_source(p)[:max_chars] for p in paths]


@click.command()
@click.argument(
    "repo_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--output-dir", "-o",
    default="./reports",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Directory for JSON reports and summary.md",
)
@click.option(
    "--project", "-p", "only_projects",
    multiple=True,
    metavar="NAME",
    help="Scan only this project (repeatable)",
)
@click.option(
    "--llm/--no-llm",
    default=False,
    help="Explicitly opt into sending source snippets to the configured model endpoint.",
)
@click.option("--verbose", "-v", is_flag=True)
def main(
    repo_path: Path,
    output_dir: Path,
    only_projects: tuple[str, ...],
    llm: bool,
    verbose: bool,
) -> None:
    """Audit agent projects in REPO_PATH for standalone LLM readiness."""
    repo_root = repo_path.absolute()
    try:
        all_projects = _discover_projects(repo_root)
    except OSError as error:
        click.echo(f"Scan not assessed: {type(error).__name__}", err=True)
        sys.exit(2)

    if only_projects:
        missing = set(only_projects) - {p.name for p in all_projects}
        if missing:
            click.echo(f"Projects not found: {', '.join(sorted(missing))}", err=True)
            sys.exit(2)
        all_projects = [p for p in all_projects if p.name in only_projects]

    if not all_projects:
        click.echo("No agent project subdirectories found.", err=True)
        sys.exit(2)

    click.echo(f"Scanning {len(all_projects)} project(s) in {repo_root}\n")

    reports = []
    for proj_dir in all_projects:
        cfg_findings, _ = scan_config_files(proj_dir)
        findings = scan_python_project(proj_dir) + scan_js_ts_project(proj_dir) + cfg_findings

        notes = ""
        if llm and not compute_verdict(proj_dir.name, findings).assessment_errors:
            snippets = _collect_snippets(proj_dir)
            prelim = compute_verdict(proj_dir.name, findings)
            notes = run_llm_pass(proj_dir.name, snippets, prelim) or ""

        report = compute_verdict(proj_dir.name, findings, notes=notes)
        out_path = write_project_report(report, output_dir)

        icon = _VERDICT_ICON.get(report.standalone_ready, "?")
        detail = (
            f"  ({len(findings)} signals, {len(report.blockers)} blockers)"
            if verbose else ""
        )
        click.echo(f"  {icon}  {proj_dir.name:<30} {report.standalone_ready}{detail}")
        if verbose and report.blockers:
            for b in report.blockers:
                click.echo(f"       [{b['severity'].upper()}] {b['type']} @ {b['location']}")

        reports.append(report)

    summary_path = write_summary(reports, output_dir)
    click.echo(f"\nReports : {output_dir}/")
    click.echo(f"Summary : {summary_path}")

    if any(r.assessment_errors for r in reports):
        sys.exit(2)
    if any(r.standalone_ready != "yes" for r in reports):
        sys.exit(1)
