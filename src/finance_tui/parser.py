"""Parse Obsidian markdown files into data models."""

import re
from datetime import date
from pathlib import Path

import yaml

from finance_tui.models import Account, Category, Transaction

# Main transaction regex:
# - [ ] `amount` [[Category]] Description ➕ YYYY-MM-DD [[Account]] 🆔 id
TRANSACTION_RE = re.compile(
    r"^- \[([ x])\] "          # checkbox
    r"`(-?\d+\.\d{2})`"        # amount in backticks
    r" \[\[(\w+)\]\]"          # category in wikilinks
    r" (.+?)"                  # description (non-greedy)
    r" ➕ (\d{4}-\d{2}-\d{2})" # date
    r" \[\[(\w+_\d+)\]\]"     # account in wikilinks
    r" 🆔 (\d+)"               # id
    r"(?: (.+))?$"             # optional tags after id
)

# Extract [[Person]] wikilinks from description
WIKILINK_RE = re.compile(r"\[\[(\w+)\]\]")

# Bizum patterns for people extraction
BIZUM_FROM_RE = re.compile(r"Bizum (?:payment from:|<) (.+)")
BIZUM_TO_RE = re.compile(r"Bizum > (.+)")
TRANSFER_TO_RE = re.compile(r"To (.+)")


def _parse_annotations(raw: str | None) -> tuple[list[str], list[str]]:
    """Parse comma-separated #tag and [[wikilink]] entries into separate lists.

    Returns (tags, links) where tags are stored without '#' and links without '[[]]'.
    """
    tags: list[str] = []
    links: list[str] = []
    if not raw:
        return tags, links
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if item.startswith("[[") and item.endswith("]]"):
            links.append(item[2:-2])
        elif item.startswith("#"):
            tags.append(item[1:])
        else:
            tags.append(item)
    return tags, links


def _extract_people(description: str) -> list[str]:
    """Extract people mentioned in a transaction description."""
    people = []

    # Extract [[Person]] wikilinks
    for match in WIKILINK_RE.finditer(description):
        people.append(match.group(1))

    # Bizum incoming: "Bizum < Name" or "Bizum payment from: Name"
    m = BIZUM_FROM_RE.match(description)
    if m:
        name = m.group(1).strip()
        # Strip wikilink syntax if present
        name = WIKILINK_RE.sub(r"\1", name)
        # Skip phone numbers
        if not name.startswith("+"):
            if name not in people:
                people.append(name)

    # Bizum outgoing: "Bizum > Name" or "Bizum > [[Name]]"
    m = BIZUM_TO_RE.match(description)
    if m:
        name = m.group(1).strip()
        name = WIKILINK_RE.sub(r"\1", name)
        if name not in people:
            people.append(name)

    # Transfer: "To [[Name]]" or "To Full Name"
    m = TRANSFER_TO_RE.match(description)
    if m:
        name = m.group(1).strip()
        name = WIKILINK_RE.sub(r"\1", name)
        if name not in people:
            people.append(name)

    return people


def parse_transaction(line: str, source_file: str, line_number: int) -> Transaction | None:
    """Parse a single transaction line. Returns None if not a transaction."""
    m = TRANSACTION_RE.match(line)
    if not m:
        return None

    validated_str, amount_str, category, description, date_str, account, id_str, annotations_raw = m.groups()
    year, month, day = date_str.split("-")
    tags, links = _parse_annotations(annotations_raw)

    return Transaction(
        id=int(id_str),
        date=date(int(year), int(month), int(day)),
        amount=float(amount_str),
        category=category,
        description=description.strip(),
        account=account,
        validated=validated_str == "x",
        source_file=source_file,
        line_number=line_number,
        raw_line=line,
        people=_extract_people(description),
        tags=tags,
        links=links,
    )


def _parse_yaml_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def parse_transaction_file(path: Path) -> list[Transaction]:
    """Parse all transactions from a single markdown file."""
    text = path.read_text(encoding="utf-8")
    source = path.name
    transactions = []
    for i, line in enumerate(text.splitlines(), start=1):
        txn = parse_transaction(line, source, i)
        if txn:
            transactions.append(txn)
    return transactions


def parse_all_transactions(transactions_dir: Path) -> list[Transaction]:
    """Parse all transaction files in the directory."""
    transactions = []
    for path in sorted(transactions_dir.glob("*.md")):
        transactions.extend(parse_transaction_file(path))
    return transactions


def parse_category_file(path: Path) -> Category:
    """Parse a category markdown file."""
    text = path.read_text(encoding="utf-8")
    meta = _parse_yaml_frontmatter(text)
    return Category(
        name=path.stem,
        budget=float(meta.get("budget", 0)),
        track=bool(meta.get("track", False)),
    )


def parse_all_categories(categories_dir: Path) -> list[Category]:
    """Parse all category files."""
    return [parse_category_file(p) for p in sorted(categories_dir.glob("*.md"))]


def parse_account_file(path: Path) -> Account:
    """Parse an account markdown file."""
    text = path.read_text(encoding="utf-8")
    meta = _parse_yaml_frontmatter(text)
    return Account(
        name=path.stem,
        aliases=meta.get("aliases", []),
    )


def parse_all_accounts(accounts_dir: Path) -> list[Account]:
    """Parse all account files."""
    return [parse_account_file(p) for p in sorted(accounts_dir.glob("*.md"))]
