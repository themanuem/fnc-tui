"""Write transaction changes back to markdown files (round-trip safe)."""

import re
from collections import defaultdict
from pathlib import Path

from finance_tui import config as cfg
from finance_tui.parser import TRANSACTION_RE


def serialize_transaction(
    validated: bool,
    amount: float,
    category: str,
    description: str,
    date_str: str,
    account: str,
    txn_id: int,
    tags: list[str] | None = None,
    links: list[str] | None = None,
) -> str:
    """Serialize a transaction to the Obsidian markdown format."""
    check = "x" if validated else " "
    line = (
        f"- [{check}] `{amount:.2f}` [[{category}]] "
        f"{description} ➕ {date_str} [[{account}]] 🆔 {txn_id}"
    )
    parts = []
    if tags:
        parts.extend(f"#{t}" for t in tags)
    if links:
        parts.extend(f"[[{l}]]" for l in links)
    if parts:
        line += " " + ", ".join(parts)
    return line


def toggle_validated(line: str) -> str:
    """Toggle the checkbox in a transaction line."""
    if "- [ ] " in line:
        return line.replace("- [ ] ", "- [x] ", 1)
    elif "- [x] " in line:
        return line.replace("- [x] ", "- [ ] ", 1)
    return line


def change_category(line: str, new_category: str) -> str:
    """Change the category in a transaction line."""
    m = TRANSACTION_RE.match(line)
    if not m:
        return line
    old_cat = m.group(3)
    return line.replace(f"[[{old_cat}]]", f"[[{new_category}]]", 1)


def update_line_in_file(
    file_path: Path,
    line_number: int,
    new_line: str,
) -> None:
    """Replace a specific line in a file (1-indexed)."""
    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    idx = line_number - 1
    if 0 <= idx < len(lines):
        # Preserve original line ending
        if lines[idx].endswith("\n"):
            new_line = new_line.rstrip("\n") + "\n"
        lines[idx] = new_line
        file_path.write_text("".join(lines), encoding="utf-8")


def update_transaction_in_file(
    source_file: str,
    line_number: int,
    new_line: str,
    transactions_dir: Path | None = None,
) -> Path:
    """Update a transaction line in its source file. Returns the file path."""
    transactions_dir = transactions_dir or cfg.TRANSACTIONS_DIR
    file_path = transactions_dir / source_file
    update_line_in_file(file_path, line_number, new_line)
    return file_path


def prepend_transaction(
    line: str,
    year: int,
    transactions_dir: Path | None = None,
) -> Path:
    """Prepend a transaction line to the year file, after YAML frontmatter."""
    transactions_dir = transactions_dir or cfg.TRANSACTIONS_DIR
    file_path = transactions_dir / f"{year}.md"
    if not file_path.exists():
        file_path.write_text(f"---\n---\n{line}\n", encoding="utf-8")
        return file_path

    text = file_path.read_text(encoding="utf-8")
    if text.startswith("---"):
        # Find end of frontmatter (second ---)
        second = text.index("---", 3)
        end_fm = text.index("\n", second) + 1
        new_text = text[:end_fm] + line + "\n" + text[end_fm:]
    else:
        new_text = line + "\n" + text
    file_path.write_text(new_text, encoding="utf-8")
    return file_path


def bulk_prepend_transactions(
    lines: list[tuple[int, str]],
    transactions_dir: Path | None = None,
    last_id: int | None = None,
) -> dict[int, Path]:
    """Prepend multiple transaction lines grouped by year.

    Args:
        lines: List of (year, serialized_line) tuples.
        last_id: If provided, update the ``last:`` frontmatter field in each written file.

    Returns:
        Dict mapping year to the file path written.
    """
    transactions_dir = transactions_dir or cfg.TRANSACTIONS_DIR
    by_year: dict[int, list[str]] = defaultdict(list)
    for year, line in lines:
        by_year[year].append(line)

    written = {}
    for year, batch in sorted(by_year.items()):
        file_path = transactions_dir / f"{year}.md"
        block = "\n".join(batch) + "\n"
        if not file_path.exists():
            fm = "---\ntags:\n  - finance/transactions\n"
            if last_id is not None:
                fm += f"last: {last_id}\n"
            fm += "---\n"
            file_path.write_text(fm + block, encoding="utf-8")
        else:
            text = file_path.read_text(encoding="utf-8")
            if text.startswith("---"):
                second = text.index("---", 3)
                end_fm = text.index("\n", second) + 1
                fm_text = text[:end_fm]
                if last_id is not None:
                    fm_text = _update_frontmatter_last(fm_text, last_id)
                text = fm_text + block + "---\n" + text[end_fm:]
            else:
                text = block + "---\n" + text
            file_path.write_text(text, encoding="utf-8")
        written[year] = file_path
    return written


def _update_frontmatter_last(fm_text: str, last_id: int) -> str:
    """Update or insert the ``last:`` field in YAML frontmatter."""
    if re.search(r"^last:\s*\d+", fm_text, re.MULTILINE):
        return re.sub(r"^last:\s*\d+", f"last: {last_id}", fm_text, count=1, flags=re.MULTILINE)
    end = fm_text.rfind("---")
    return fm_text[:end] + f"last: {last_id}\n" + fm_text[end:]


def write_category_file(
    name: str,
    budget: float,
    track: bool,
    categories_dir: Path | None = None,
) -> Path:
    """Create or update a category .md file with YAML frontmatter."""
    categories_dir = categories_dir or cfg.CATEGORIES_DIR
    file_path = categories_dir / f"{name}.md"
    lines = ["---"]
    if budget:
        lines.append(f"budget: {budget}")
    if track:
        lines.append("track: true")
    lines.append("---\n")
    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


def delete_category_file(
    name: str,
    categories_dir: Path | None = None,
) -> None:
    """Delete a category .md file."""
    categories_dir = categories_dir or cfg.CATEGORIES_DIR
    file_path = categories_dir / f"{name}.md"
    if file_path.exists():
        file_path.unlink()


def rename_category_everywhere(
    old_name: str,
    new_name: str,
    categories_dir: Path | None = None,
    transactions_dir: Path | None = None,
) -> list[Path]:
    """Rename category file and propagate across all transaction files.

    Returns list of all modified file paths.
    """
    categories_dir = categories_dir or cfg.CATEGORIES_DIR
    transactions_dir = transactions_dir or cfg.TRANSACTIONS_DIR
    modified = []

    old_path = categories_dir / f"{old_name}.md"
    new_path = categories_dir / f"{new_name}.md"
    if old_path.exists():
        text = old_path.read_text(encoding="utf-8")
        new_path.write_text(text, encoding="utf-8")
        old_path.unlink()
        modified.append(new_path)

    old_ref = f"[[{old_name}]]"
    new_ref = f"[[{new_name}]]"
    for md_file in sorted(transactions_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        if old_ref in content:
            content = content.replace(old_ref, new_ref)
            md_file.write_text(content, encoding="utf-8")
            modified.append(md_file)

    return modified
