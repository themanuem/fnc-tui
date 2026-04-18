"""Entry point for finance_tui — TUI app and CLI import command."""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="fnc",
        description="Personal finance TUI and import tool",
    )
    sub = parser.add_subparsers(dest="command")

    imp = sub.add_parser("import", help="Import transactions from a file")
    imp.add_argument("file", type=Path, help="Path to .csv, .json, .xlsx, or .md file")
    imp.add_argument("--account", required=True, help="Account ID (e.g. BBVA_01)")
    imp.add_argument("--category", default="Other", help="Default category (default: Other)")
    imp.add_argument("--provider", choices=["ollama", "anthropic"], default=None,
                     help="LLM provider for column detection (default: auto-detect)")
    imp.add_argument("--model", default=None, help="LLM model name")
    imp.add_argument("--date-col", default=None, help="Override date column (skip LLM)")
    imp.add_argument("--desc-col", default=None, help="Override description column (skip LLM)")
    imp.add_argument("--amount-col", default=None, help="Override amount column (skip LLM)")
    imp.add_argument("--debit-col", default=None, help="Override debit column (skip LLM)")
    imp.add_argument("--credit-col", default=None, help="Override credit column (skip LLM)")
    imp.add_argument("--no-preview", action="store_true", help="Skip preview, write immediately")
    imp.add_argument("--dry-run", action="store_true", help="Preview only, don't write")

    args = parser.parse_args()

    if args.command == "import":
        from finance_tui.config import is_configured
        if not is_configured():
            print("Finance directory not configured. Run `fnc` first to complete setup.", file=sys.stderr)
            sys.exit(1)
        _run_import(args)
    else:
        from finance_tui.app import FinanceTUI
        app = FinanceTUI()
        app.run()


def _run_import(args):
    from rich.console import Console
    from rich.table import Table

    from finance_tui.config import TRANSACTIONS_DIR
    from finance_tui.importers.mapper import ColumnMapping, detect_columns
    from finance_tui.importers.llm import Provider, detect_provider
    from finance_tui.importers.readers import read_file
    from finance_tui.importers.transformer import detect_duplicates, transform
    from finance_tui.store import FinanceStore
    from finance_tui.writer import bulk_prepend_transactions, serialize_transaction

    console = Console()

    if not args.file.exists():
        console.print(f"[red]File not found:[/] {args.file}")
        sys.exit(1)

    console.print(f"Reading [bold]{args.file.name}[/]...")
    try:
        df = read_file(args.file)
    except (ValueError, ImportError) as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    console.print(f"  {len(df)} rows, columns: {list(df.columns)}")

    has_manual = args.date_col and args.desc_col and (args.amount_col or (args.debit_col and args.credit_col))
    if has_manual:
        mapping = ColumnMapping(
            date_col=args.date_col,
            description_col=args.desc_col,
            amount_col=args.amount_col,
            debit_col=args.debit_col,
            credit_col=args.credit_col,
        )
        mapping.validate()
        console.print("[dim]Using manual column mapping[/]")
    else:
        provider_arg = Provider(args.provider) if args.provider else None
        provider = provider_arg or detect_provider()
        if provider is None:
            console.print(
                "[red]No LLM available.[/] Install Ollama or set ANTHROPIC_API_KEY.\n"
                "Or specify columns manually: --date-col, --desc-col, --amount-col"
            )
            sys.exit(1)
        console.print(f"Detecting columns via [bold]{provider.value}[/]...")
        try:
            mapping = detect_columns(df, provider=provider, model=args.model)
        except Exception as e:
            console.print(f"[red]Column detection failed:[/] {e}")
            sys.exit(1)

    # Show mapping
    mapping_parts = [f"Date: [cyan]{mapping.date_col}[/]", f"Description: [cyan]{mapping.description_col}[/]"]
    if mapping.is_split:
        mapping_parts.append(f"Debit: [cyan]{mapping.debit_col}[/]")
        mapping_parts.append(f"Credit: [cyan]{mapping.credit_col}[/]")
    else:
        mapping_parts.append(f"Amount: [cyan]{mapping.amount_col}[/]")
    console.print("  " + " | ".join(mapping_parts))

    if not has_manual and not args.no_preview:
        resp = input("\nConfirm mapping? [Y/n/manual] ").strip().lower()
        if resp == "manual":
            console.print("[dim]Use --date-col, --desc-col, --amount-col flags to specify manually.[/]")
            sys.exit(0)
        if resp and resp != "y":
            console.print("[dim]Aborted.[/]")
            sys.exit(0)

    console.print("Transforming...")
    txns = transform(df, mapping, args.account, category=args.category)

    # Duplicate detection
    try:
        store = FinanceStore()
        dupes = detect_duplicates(txns, store.df)
    except Exception:
        dupes = []

    # Preview
    if not args.no_preview:
        table = Table(title=f"Preview ({min(10, len(txns))} of {len(txns)} transactions)")
        table.add_column("Date", style="cyan")
        table.add_column("Description")
        table.add_column("Amount", justify="right")
        table.add_column("Account", style="dim")
        for t in txns[:10]:
            color = "green" if t.amount > 0 else "red"
            table.add_row(
                t.date.isoformat(),
                t.description,
                f"[{color}]{t.amount:.2f}[/]",
                t.account,
            )
        console.print(table)

        total = sum(t.amount for t in txns)
        console.print(f"\n  Total: [bold]{total:.2f}[/] | Count: [bold]{len(txns)}[/]")

        if dupes:
            console.print(f"\n[yellow]Warning:[/] {len(dupes)} potential duplicate(s) detected:")
            for d in dupes[:5]:
                console.print(f"  {d['new'].date} {d['new'].amount:.2f} ~ existing #{d['existing_id']} ({d['similarity']:.0%} match)")

    if args.dry_run:
        console.print("\n[dim]Dry run — no files written.[/]")
        return

    if not args.no_preview:
        resp = input("\nWrite to disk? [Y/n] ").strip().lower()
        if resp and resp != "y":
            console.print("[dim]Aborted.[/]")
            return

    lines = []
    for t in txns:
        serialized = serialize_transaction(
            t.validated, t.amount, t.category, t.description,
            t.date.isoformat(), t.account, t.id,
        )
        lines.append((t.date.year, serialized))

    written = bulk_prepend_transactions(lines, TRANSACTIONS_DIR)
    files = ", ".join(str(p.name) for p in written.values())
    console.print(f"\n[green]Done![/] {len(txns)} transactions written to {files}")


if __name__ == "__main__":
    main()
