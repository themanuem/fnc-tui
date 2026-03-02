"""Write transaction changes back to markdown files (round-trip safe)."""

import re
from pathlib import Path

from finance_tui.config import TRANSACTIONS_DIR
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
    transactions_dir: Path = TRANSACTIONS_DIR,
) -> Path:
    """Update a transaction line in its source file. Returns the file path."""
    file_path = transactions_dir / source_file
    update_line_in_file(file_path, line_number, new_line)
    return file_path


def prepend_transaction(
    line: str,
    year: int,
    transactions_dir: Path = TRANSACTIONS_DIR,
) -> Path:
    """Prepend a transaction line to the year file, after YAML frontmatter."""
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
