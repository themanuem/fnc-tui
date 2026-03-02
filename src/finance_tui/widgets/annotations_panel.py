"""Annotations panel - tags and links breakdown with amounts and counts."""

from rich.text import Text

from finance_tui import analytics
from finance_tui.config import CURRENCY
from finance_tui.widgets.panel_table import PanelTable

_BAR_WIDTH = 12
_FILL = "▪"
_EMPTY = "·"


class AnnotationsPanel(PanelTable):
    """Joint tags & links breakdown with amount totals and transaction counts."""

    def __init__(self, df, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self.border_title = "Tags & Links"

    def on_mount(self) -> None:
        self._initial_row_count = 0
        self._build_rows()

    def _build_rows(self) -> None:
        df = self._df
        rows: list[tuple[Text, str]] = []

        if df is not None and not df.empty:
            tag_data = self._aggregate(df, "tags", "#")
            link_data = self._aggregate(df, "links", "[[")

            all_items = tag_data + link_data
            max_abs = max((abs(d["amount"]) for d in all_items), default=1) or 1

            for item in all_items:
                pct = abs(item["amount"]) / max_abs
                filled = max(1, int(pct * _BAR_WIDTH))
                empty = _BAR_WIDTH - filled

                line = Text()
                line.append(f" {item['label']:16s} ", style=item["color"])
                line.append(_FILL * filled, style=item["bar_color"])
                line.append(_EMPTY * empty, style="#2A2A2A")
                line.append(f" {item['amount']:>10,.2f} {CURRENCY} ", style="#E0E0E0")
                line.append(f"({item['count']})", style="#555555")

                rows.append((line, item["filter"]))

        if not self._initial_row_count:
            self._initial_row_count = len(rows)

        while len(rows) < self._initial_row_count:
            rows.append((Text(""), ""))

        self._load_rows(rows)

    @staticmethod
    def _aggregate(df, field: str, prefix: str) -> list[dict]:
        """Aggregate amounts and counts for a list-type column (tags or links)."""
        if field not in df.columns:
            return []

        totals: dict[str, float] = {}
        counts: dict[str, int] = {}

        for _, row in df.iterrows():
            items = row.get(field, [])
            if not isinstance(items, list):
                continue
            for name in items:
                totals[name] = totals.get(name, 0.0) + row["amount"]
                counts[name] = counts.get(name, 0) + 1

        if not totals:
            return []

        is_tag = prefix == "#"
        color = "#4FC1E9" if is_tag else "#AC92EC"
        bar_color = "#4FC1E9" if is_tag else "#AC92EC"
        filter_prefix = "tag" if is_tag else "link"

        result = []
        for name in sorted(totals.keys(), key=lambda n: abs(totals[n]), reverse=True):
            label = name
            result.append({
                "label": label,
                "amount": totals[name],
                "count": counts[name],
                "color": color,
                "bar_color": bar_color,
                "filter": f"{filter_prefix}:{name}",
            })

        return result

    def refresh_data(self, df):
        self._df = df
        self._build_rows()
