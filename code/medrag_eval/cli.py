from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import db
from .config import DEFAULT_DB_PATH, Settings
from .excel_io import import_questions_from_workbook
from .export import export_raw, export_summary
from .prompting import SHARED_PROMPT_VERSION
from .providers import get_provider, normalize_provider_name
from .runner import parse_provider_models, run_benchmark

app = typer.Typer(no_args_is_help=True)
console = Console()


def db_option() -> Path:
    return Path(DEFAULT_DB_PATH)


@app.command("init-db")
def init_db(db_path: Annotated[Path, typer.Option("--db", help="SQLite database path.")] = Path(DEFAULT_DB_PATH)) -> None:
    """Create or migrate the SQLite database."""
    db.init_db(db_path)
    console.print(f"Database ready: {db_path}")


@app.command("check-auth")
def check_auth(
    provider: Annotated[str, typer.Option("--provider", help="Provider name: tailscale or openrouter.")],
) -> None:
    """Check provider credentials without running a benchmark."""
    settings = Settings.from_env()
    adapter = get_provider(provider, settings=settings)
    try:
        adapter.healthcheck()
    except RuntimeError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(f"{normalize_provider_name(provider)} auth check passed")


@app.command("import-questions")
def import_questions(
    dataset: Annotated[str, typer.Option("--dataset", help="Dataset name.")],
    xlsx: Annotated[Optional[Path], typer.Argument(help="Excel workbook path.")] = None,
    xlsx_option: Annotated[Optional[Path], typer.Option("--xlsx", help="Excel workbook path.")] = None,
    db_path: Annotated[Path, typer.Option("--db", help="SQLite database path.")] = Path(DEFAULT_DB_PATH),
) -> None:
    """Import scoreable workbook rows into SQLite."""
    workbook_path = xlsx_option or xlsx
    if workbook_path is None:
        raise typer.BadParameter("Provide a workbook path as an argument or with --xlsx")
    db.init_db(db_path)
    imported = import_questions_from_workbook(workbook_path)
    with db.connect(db_path) as conn:
        dataset_id = db.upsert_dataset(conn, name=dataset, source_xlsx_path=str(workbook_path), row_count=len(imported.questions))
        db.replace_questions(conn, dataset_id, imported.questions)
    for warning in imported.warnings:
        console.print(f"[yellow]warning:[/yellow] {warning}")
    console.print(f"Imported {len(imported.questions)} scoreable questions into dataset {dataset}")


@app.command("run")
def run(
    dataset: Annotated[str, typer.Option("--dataset")],
    experiment_name: Annotated[str, typer.Option("--experiment-name")],
    providers: Annotated[Optional[str], typer.Option("--providers", help="Comma-separated providers.")] = None,
    models: Annotated[Optional[str], typer.Option("--models", help="Comma-separated models aligned with providers.")] = None,
    provider_model: Annotated[list[str], typer.Option("--provider-model", help="provider:model pair; repeatable.")] = [],
    runs: Annotated[int, typer.Option("--runs", min=1)] = 1,
    limit: Annotated[Optional[int], typer.Option("--limit", min=1)] = None,
    offset: Annotated[int, typer.Option("--offset", min=0)] = 0,
    question_id: Annotated[Optional[str], typer.Option("--question-id")] = None,
    temperature: Annotated[float, typer.Option("--temperature")] = 0,
    prompt_version: Annotated[str, typer.Option("--prompt-version", help="Shared prompt regime used by every arm (user-only, English instructions, JSON output contract, Spanish content). Both providers receive identical messages.")] = SHARED_PROMPT_VERSION,
    tailscale_prompt_id: Annotated[Optional[int], typer.Option("--tailscale-prompt-id", help="GIFT MCQ prompt ID. GIFT runs default to the required ID 13; any other value is rejected.")] = None,
    tailscale_top_k: Annotated[Optional[int], typer.Option("--tailscale-top-k", help="Retrieval depth for TailScale (X-Top-K header). Optional.", min=1)] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry")] = False,
    openrouter_concurrency: Annotated[int, typer.Option("--openrouter-concurrency", help="Maximum concurrent OpenRouter calls.", min=1, max=64)] = 18,
    tailscale_concurrency: Annotated[int, typer.Option("--tailscale-concurrency", help="Maximum concurrent TailScale calls.", min=1, max=16)] = 5,
    db_path: Annotated[Path, typer.Option("--db")] = Path(DEFAULT_DB_PATH),
) -> None:
    """Run or plan benchmark calls.

    Methodology:
    - Both providers receive identical messages: a single user role carrying
      English instructions, the JSON output contract, and the Spanish question
      content (default: mcq_shared_v2). Neither receives a system role.
    - TailScale additionally sends X-Prompt-ID: 13 (and optionally X-Top-K) so
      the backend uses the stored multiple-choice prompt instead of Conciso.
    - OpenRouter retains response_format: json_schema enforcement. TailScale
      does not honor it per the API characterization. This is the one
      remaining asymmetry between arms and is recorded in the DB.
    """
    db.init_db(db_path)
    pairs = parse_provider_models(providers, models, tuple(provider_model))
    summary = run_benchmark(
        db_path=db_path,
        dataset=dataset,
        experiment_name=experiment_name,
        provider_models=pairs,
        runs=runs,
        limit=limit,
        offset=offset,
        question_id=question_id,
        temperature=temperature,
        prompt_version=prompt_version,
        force=force,
        dry_run=dry_run,
        no_retry=no_retry,
        openrouter_concurrency=openrouter_concurrency,
        tailscale_concurrency=tailscale_concurrency,
        tailscale_prompt_id=tailscale_prompt_id,
        tailscale_top_k=tailscale_top_k,
    )
    console.print(
        f"planned={summary.planned_calls} executed={summary.executed_calls} "
        f"skipped={summary.skipped_calls} dry_run={summary.dry_run}"
    )


@app.command("status")
def status(
    experiment_name: Annotated[str, typer.Option("--experiment-name")],
    db_path: Annotated[Path, typer.Option("--db")] = Path(DEFAULT_DB_PATH),
) -> None:
    """Show benchmark progress and accuracy metrics."""
    with db.connect(db_path) as conn:
        rows = db.status_rows(conn, experiment_name)
        totals = db.status_totals(conn, experiment_name)
    total_values = dict(totals)
    console.print(
        f"planned={_number(total_values.get('planned'))} completed={_number(total_values.get('completed'))} "
        f"api_failed={_number(total_values.get('api_failed'))} parse_failed={_number(total_values.get('parse_failed'))} "
        f"skipped_by_resume={_number(total_values.get('skipped_by_resume'))}"
    )
    table = Table("provider", "model", "calls", "parse_success_rate", "strict_accuracy", "mean_latency_ms")
    for row in rows:
        table.add_row(
            row["provider"],
            row["model"],
            str(row["calls"]),
            _pct(row["parse_success_rate"]),
            _pct(row["strict_accuracy"]),
            str(row["mean_latency_ms"] or ""),
        )
    console.print(table)


@app.command("export")
def export(
    experiment_name: Annotated[str, typer.Option("--experiment-name")],
    format: Annotated[str, typer.Option("--format", help="csv, xlsx, or jsonl")],
    out: Annotated[Optional[Path], typer.Option("--out")] = None,
    db_path: Annotated[Path, typer.Option("--db")] = Path(DEFAULT_DB_PATH),
) -> None:
    """Export summary CSV/XLSX or raw attempts JSONL."""
    if format == "jsonl":
        path = export_raw(db_path, experiment_name=experiment_name, out=out)
    elif format in {"csv", "xlsx"}:
        path = export_summary(db_path, experiment_name=experiment_name, fmt=format, out=out)
    else:
        raise typer.BadParameter("--format must be csv, xlsx, or jsonl")
    console.print(f"Wrote {path}")


@app.command("inspect-call")
def inspect_call(
    call_id: Annotated[int, typer.Argument(help="Logical benchmark call id.")],
    db_path: Annotated[Path, typer.Option("--db")] = Path(DEFAULT_DB_PATH),
) -> None:
    """Print stored attempts, parse result, and score for a logical call."""
    with db.connect(db_path) as conn:
        try:
            payload = db.inspect_logical_call(conn, call_id)
        except KeyError as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(1) from exc
    console.print_json(data=payload)


def _pct(value) -> str:
    if value is None:
        return ""
    return f"{float(value) * 100:.1f}%"


def _number(value) -> int:
    return int(value or 0)


if __name__ == "__main__":
    app()
