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
from .scanner.python_ast import scan_python_project
from .scanner.ripgrep import scan_js_ts_project
from .verdict import compute_verdict

_VERDICT_ICON = {"yes": "✅", "partial": "⚠️", "no": "❌"}

# Directories that are never agent projects
_IGNORED_DIRS: frozenset[str] = frozenset(
    {".git", ".github", ".venv", "venv", "node_modules", "__pycache__",
     "reports", "docs", ".tox", "dist", "build"}
)


def _discover_projects(repo_root: Path) -> list[Path]:
    """Return projects to scan.

    Monorepo: returns immediate subdirectories that contain source code.
    Single-project repo: if no subdirectories qualify, falls back to root.
    """
    candidates: list[Path] = []
    for child in sorted(repo_root.iterdir()):
        if not child.is_dir() or child.name in _IGNORED_DIRS:
            continue
        has_code = (
            any(child.rglob("*.py"))
            or any(child.rglob("*.ts"))
            or any(child.rglob("*.js"))
        )
        if has_code:
            candidates.append(child)

    # Single-project repo: no qualifying subdirs → treat root as the project
    if not candidates:
        root_has_code = (
            any(repo_root.glob("*.py"))
            or any(repo_root.glob("*.ts"))
            or any(repo_root.glob("*.js"))
        )
        if root_has_code:
            candidates.append(repo_root)

    return candidates


def _collect_snippets(proj_dir: Path, max_files: int = 8, max_chars: int = 500) -> list[str]:
    snippets: list[str] = []
    for py in list(proj_dir.rglob("*.py"))[:max_files]:
        try:
            snippets.append(py.read_text(encoding="utf-8", errors="replace")[:max_chars])
        except OSError:
            pass
    return snippets


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
    "--no-llm",
    is_flag=True,
    help="Skip the LLM refinement pass (zero network required)",
)
@click.option("--verbose", "-v", is_flag=True)
def main(
    repo_path: Path,
    output_dir: Path,
    only_projects: tuple[str, ...],
    no_llm: bool,
    verbose: bool,
) -> None:
    """Audit agent projects in REPO_PATH for standalone LLM readiness."""
    repo_root = repo_path.resolve()
    all_projects = _discover_projects(repo_root)

    if only_projects:
        all_projects = [p for p in all_projects if p.name in only_projects]
        if not all_projects:
            click.echo(
                f"No projects matched: {', '.join(only_projects)}", err=True
            )
            sys.exit(1)

    if not all_projects:
        click.echo("No agent project subdirectories found.", err=True)
        sys.exit(1)

    click.echo(f"Scanning {len(all_projects)} project(s) in {repo_root}\n")

    reports = []
    for proj_dir in all_projects:
        cfg_findings, _ = scan_config_files(proj_dir)
        findings = scan_python_project(proj_dir) + scan_js_ts_project(proj_dir) + cfg_findings

        notes = ""
        if not no_llm:
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
