"""Evolution line chart - monthly/daily running balance with period-based navigation."""

import calendar
import math

from rich.text import Text
from textual.binding import Binding
from textual.events import MouseScrollDown, MouseScrollUp
from textual.app import RenderResult
from textual_plotext import PlotextPlot

from finance_tui import analytics

# Shade endpoints for trend coloring
_GREEN_DIM = (35, 70, 35)
_GREEN_BRIGHT = (92, 184, 92)
_RED_DIM = (70, 35, 35)
_RED_BRIGHT = (217, 83, 79)

_NICE = [1, 2, 5]


def _nice_step(max_val: float, target_ticks: int = 5) -> int:
    """Pick a clean step for y-axis ticks (1/2/5 x 10^n)."""
    if max_val <= 0:
        return 1
    raw = max_val / target_ticks
    exp = math.floor(math.log10(raw))
    magnitude = 10 ** exp
    residual = raw / magnitude
    step = 10 * magnitude  # fallback
    for n in _NICE:
        if residual <= n:
            step = int(n * magnitude)
            break
    if max_val >= 1000 and step < 1000:
        step = 1000
    return max(step, 1)


def _fmt_tick(val: float) -> str:
    """Format tick value as max-4-char abbreviated string.

    Budget: 4 chars total. Negative sign steals 1, so negative values
    drop the decimal part to stay within 4.
    """
    v = int(val)
    av = abs(v)
    neg = v < 0
    if av >= 1_000_000:
        whole, frac = divmod(av, 1_000_000)
        if frac == 0 or neg:
            s = f"{whole}M"
        else:
            tenths = round(frac / 100_000)
            if tenths == 10:
                s = f"{whole + 1}M"
            else:
                s = f"{whole}.{tenths}M"
    elif av >= 1_000:
        whole, frac = divmod(av, 1_000)
        if frac == 0 or neg:
            s = f"{whole}k"
        else:
            tenths = round(frac / 100)
            if tenths == 10:
                s = f"{whole + 1}k"
            else:
                s = f"{whole}.{tenths}k"
    else:
        s = str(av)
    return f"-{s}" if neg else s


def _lerp_color(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    """Linear interpolation between two RGB colors."""
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


class EvolutionChart(PlotextPlot):
    """Line chart showing cumulative balance over time with period-based navigation."""

    can_focus = True

    BINDINGS = [
        Binding("a", "set_scale('all')", "All", show=False),
        Binding("y", "set_scale('year')", "Year", show=False),
        Binding("m", "set_scale('month')", "Month", show=False),
        Binding("f", "toggle_y_mode", "Y-Fit", show=False),
        Binding("left", "page_prev", "Prev", show=False),
        Binding("right", "page_next", "Next", show=False),
        Binding("home", "page_first", "First", show=False),
        Binding("end", "page_last", "Last", show=False),
        Binding("enter", "apply_period", "Apply", show=False),
    ]

    _SCALE_LABELS = {"all": "All", "year": "Year", "month": "Month"}

    def __init__(self, df, **kwargs):
        super().__init__(**kwargs)
        self._df = df
        self._scale = "all"
        self._y_auto = True
        self._page_index = -1  # -1 means last page (most recent)

    def render(self) -> RenderResult:
        """Override to apply muted colors that blend with $bg-panel."""
        p = self._plot
        p.plotsize(self.size.width, self.size.height)
        p._set_size(self.size.width, self.size.height)
        p.theme("clear")
        # axes_color = bg for axis area (must match $bg-panel to be invisible)
        # canvas_color = bg for plot area
        # ticks_color = fg for frame lines, tick labels, and grid lines
        p.canvas_color((26, 26, 26))
        p.axes_color((26, 26, 26))
        p.ticks_color((85, 85, 85))
        return Text.from_ansi(p.build())

    def on_mount(self):
        self._update_title()
        self._draw()

    # --- Title & subtitle ---

    def _update_title(self):
        scale = self._SCALE_LABELS.get(self._scale, "All")
        ymode = "Auto-Y" if self._y_auto else "Fixed-Y"
        self.border_title = f"3·Balance Evolution · {scale} · {ymode}"

    def _update_subtitle(self, pages, page_idx):
        if self._scale == "all":
            self.border_subtitle = ""
            return
        if not pages:
            self.border_subtitle = ""
            return
        labels, _ = pages[page_idx]
        # Show parent period as context hint
        t = Text()
        if len(pages) > 1 and page_idx > 0:
            t.append("\u25c0 ", style="#555555")
        if self._scale == "year":
            t.append(labels[0][:4], style="#777777")  # YYYY
        elif self._scale == "month":
            import calendar as _cal
            yr, mon = int(labels[0][:4]), int(labels[0][5:7])
            t.append(f"{_cal.month_name[mon]} {yr}", style="#777777")
        if len(pages) > 1:
            t.append(f"  {page_idx + 1}/{len(pages)}", style="#555555")
            if page_idx < len(pages) - 1:
                t.append(" \u25b6", style="#555555")
        self.border_subtitle = t

    # --- Data & paging ---

    def _get_all_data(self):
        """Return (labels, values) for the full dataset at current granularity."""
        if self._scale == "month":
            data = analytics.daily_running_balance(self._df)
            labels = data["day"].tolist() if not data.empty else []
        else:
            data = analytics.monthly_running_balance(self._df)
            labels = data["month"].tolist() if not data.empty else []
        values = data["cumulative"].tolist() if not data.empty else []
        return labels, values

    def _build_pages(self, labels, values):
        """Split data into fixed-length pages based on scale mode.

        Year pages always have 12 month slots (Jan-Dec).
        Month pages always have N day slots (1-28/29/30/31).
        Missing slots get None values.
        Returns list of (labels, values) tuples.
        """
        if not labels:
            return []

        if self._scale == "all":
            return [(labels, values)]

        # Build lookup from label → value
        lookup = dict(zip(labels, values))

        if self._scale == "year":
            # Determine year range from data
            years = sorted({lbl[:4] for lbl in labels})
            pages = []
            for year in years:
                page_labels = [f"{year}-{m:02d}" for m in range(1, 13)]
                page_values = [lookup.get(lbl) for lbl in page_labels]
                pages.append((page_labels, page_values))
            return pages

        if self._scale == "month":
            # Determine month range from data
            months = sorted({lbl[:7] for lbl in labels})
            pages = []
            for month_str in months:
                year, mon = int(month_str[:4]), int(month_str[5:7])
                days_in_month = calendar.monthrange(year, mon)[1]
                page_labels = [f"{month_str}-{d:02d}" for d in range(1, days_in_month + 1)]
                page_values = [lookup.get(lbl) for lbl in page_labels]
                pages.append((page_labels, page_values))
            return pages

        return [(labels, values)]

    def _resolve_page_index(self, pages):
        """Clamp page index and resolve -1 to last page."""
        if not pages:
            return 0
        if self._page_index < 0:
            self._page_index = len(pages) - 1
        self._page_index = max(0, min(self._page_index, len(pages) - 1))
        return self._page_index

    # --- Drawing ---

    def _draw(self):
        all_labels, all_values = self._get_all_data()
        if not all_values:
            return

        pages = self._build_pages(all_labels, all_values)
        if not pages:
            return

        page_idx = self._resolve_page_index(pages)
        labels, values = pages[page_idx]

        p = self.plt
        p.clear_figure()

        # Frame: left + bottom only
        p.xaxes(True, False)
        p.yaxes(True, False)

        # Horizontal gridlines
        p.grid(True, False)

        x = list(range(len(values)))

        # Filter non-None data points for plotting
        real = [(i, v) for i, v in enumerate(values) if v is not None]

        if len(real) < 2:
            if real:
                p.plot([real[0][0]], [real[0][1]], color=(119, 119, 119), marker="braille")
            # Set xlim to show full fixed-width axis even with sparse data
            if len(values) > 1:
                p.xlim(0, len(values) - 1)
        else:
            diffs = [real[j][1] - real[j - 1][1] for j in range(1, len(real))]
            max_abs = max(abs(d) for d in diffs) or 1

            for j in range(1, len(real)):
                diff = real[j][1] - real[j - 1][1]
                ratio = min(abs(diff) / max_abs, 1.0)
                if diff >= 0:
                    color = _lerp_color(_GREEN_DIM, _GREEN_BRIGHT, ratio)
                else:
                    color = _lerp_color(_RED_DIM, _RED_BRIGHT, ratio)
                p.plot(
                    [real[j - 1][0], real[j][0]],
                    [real[j - 1][1], real[j][1]],
                    color=color,
                    marker="braille",
                )
            # Ensure x-axis spans full period width
            p.xlim(0, len(values) - 1)

        # Y-axis — use only non-None values
        if self._y_auto:
            y_values = [v for v in values if v is not None]
        else:
            y_values = [v for v in all_values if v is not None]
        if not y_values:
            y_values = [0]

        max_v = max(y_values)
        min_v = min(min(y_values), 0)
        extent = max(abs(max_v), abs(min_v), 1)
        step = _nice_step(extent)
        y_top = math.ceil(max_v / step) * step if max_v > 0 else step
        y_bottom = math.floor(min_v / step) * step if min_v < 0 else 0
        if y_top == y_bottom:
            y_top = y_bottom + step
        ytick_vals = list(range(y_bottom, y_top + 1, step))
        ytick_labels = [_fmt_tick(v).rjust(5) for v in ytick_vals]
        p.ylim(y_bottom, y_top)
        p.yticks(ytick_vals, ytick_labels)

        # X-axis — equidistant, format adapted to scale
        tick_indices = list(range(len(labels)))
        if self._scale == "all":
            # Show YYYY, one tick per unique year
            seen = set()
            filtered_idx, filtered_lbl = [], []
            for i, lbl in enumerate(labels):
                yr = lbl[:4]
                if yr not in seen:
                    seen.add(yr)
                    filtered_idx.append(i)
                    filtered_lbl.append(yr)
            p.xticks(filtered_idx, filtered_lbl)
        elif self._scale == "year":
            # Zero-padded month numbers (01..12)
            display = [lbl[5:7] for lbl in labels]
            p.xticks(tick_indices, display)
        elif self._scale == "month":
            # Show day numbers (1..31), every label
            display = [str(int(lbl[8:10])) for lbl in labels]
            p.xticks(tick_indices, display)

        self._update_subtitle(pages, page_idx)

    # --- Public API ---

    def refresh_data(self, df):
        self._df = df
        self._draw()
        self.refresh()

    # --- Actions ---

    def action_set_scale(self, scale: str):
        if scale == self._scale:
            return
        self._scale = scale
        self._page_index = -1  # reset to most recent
        self._update_title()
        self._draw()
        self.refresh()

    def action_toggle_y_mode(self):
        self._y_auto = not self._y_auto
        self._update_title()
        self._draw()
        self.refresh()

    def _navigate_page(self, delta: int):
        if self._scale == "all":
            return
        all_labels, all_values = self._get_all_data()
        pages = self._build_pages(all_labels, all_values)
        if len(pages) <= 1:
            return
        old = self._resolve_page_index(pages)
        self._page_index = max(0, min(old + delta, len(pages) - 1))
        if self._page_index != old:
            self._draw()
            self.refresh()

    def action_page_prev(self):
        self._navigate_page(-1)

    def action_page_next(self):
        self._navigate_page(1)

    def action_page_first(self):
        self._navigate_page(-99999)

    def action_page_last(self):
        self._navigate_page(99999)

    def action_apply_period(self):
        """Set the app's period selector to match the current chart page."""
        if self._scale == "all":
            return
        all_labels, all_values = self._get_all_data()
        pages = self._build_pages(all_labels, all_values)
        if not pages:
            return
        page_idx = self._resolve_page_index(pages)
        labels, _ = pages[page_idx]
        try:
            from finance_tui.widgets.period_selector import PeriodSelector
            selector = self.app.query_one("#period", PeriodSelector)
            if self._scale == "year":
                selector._year = int(labels[0][:4])
                selector.mode = "year"
            elif self._scale == "month":
                selector._year = int(labels[0][:4])
                selector._month = int(labels[0][5:7])
                selector.mode = "month"
        except Exception:
            pass

    # --- Mouse scroll ---

    def on_mouse_scroll_down(self, event: MouseScrollDown):
        if self._scale != "all":
            self._navigate_page(1)
            event.stop()

    def on_mouse_scroll_up(self, event: MouseScrollUp):
        if self._scale != "all":
            self._navigate_page(-1)
            event.stop()
