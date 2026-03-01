"""Time period picker widget."""

from datetime import date

from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class PeriodSelector(Static):
    """Compact period selector. [/] to navigate, a/y/m to switch mode."""

    class PeriodChanged(Message):
        def __init__(self, start: date | None, end: date | None, label: str):
            super().__init__()
            self.start = start
            self.end = end
            self.label = label

    mode = reactive("all")
    _year = reactive(date.today().year)
    _month = reactive(date.today().month)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._update_label()

    def _update_label(self):
        if self.mode == "all":
            label = "All Time"
        elif self.mode == "year":
            label = str(self._year)
        else:
            label = f"{self._year}-{self._month:02d}"
        self.update(f"◀ {label} ▶")

    def watch_mode(self):
        self._update_label()
        self._emit()

    def watch__year(self):
        self._update_label()
        self._emit()

    def watch__month(self):
        self._update_label()
        self._emit()

    def _emit(self):
        if self.mode == "all":
            self.post_message(self.PeriodChanged(None, None, "All Time"))
        elif self.mode == "year":
            self.post_message(self.PeriodChanged(
                date(self._year, 1, 1), date(self._year, 12, 31), str(self._year)
            ))
        else:
            start = date(self._year, self._month, 1)
            end = date(self._year + 1, 1, 1) if self._month == 12 else date(self._year, self._month + 1, 1)
            self.post_message(self.PeriodChanged(
                start, end, f"{self._year}-{self._month:02d}"
            ))

    def action_prev(self):
        if self.mode == "year":
            self._year -= 1
        elif self.mode == "month":
            if self._month == 1:
                self._month = 12
                self._year -= 1
            else:
                self._month -= 1

    def action_next(self):
        if self.mode == "year":
            self._year += 1
        elif self.mode == "month":
            if self._month == 12:
                self._month = 1
                self._year += 1
            else:
                self._month += 1

    def action_set_all(self):
        self.mode = "all"

    def action_set_year(self):
        self.mode = "year"

    def action_set_month(self):
        self.mode = "month"
