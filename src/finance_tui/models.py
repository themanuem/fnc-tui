"""Data models for transactions, accounts, and categories."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Transaction:
    id: int
    date: date
    amount: float
    category: str
    description: str
    account: str
    validated: bool
    source_file: str
    line_number: int
    raw_line: str
    people: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)   # #tag entries (stored without #)
    links: list[str] = field(default_factory=list)  # [[wikilink]] entries (stored without brackets)

    @property
    def is_expense(self) -> bool:
        return self.amount < 0

    @property
    def is_income(self) -> bool:
        return self.amount > 0

    @property
    def month(self) -> str:
        return self.date.strftime("%Y-%m")


@dataclass
class Account:
    name: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class Category:
    name: str
    budget: float = 0.0
    track: bool = False
