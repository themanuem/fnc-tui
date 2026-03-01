"""Amount frequency histogram widget."""

from textual_plotext import PlotextPlot


class AmountHistogram(PlotextPlot):
    """Histogram showing distribution of transaction amounts."""

    def __init__(self, df, **kwargs):
        super().__init__(**kwargs)
        self._df = df

    def on_mount(self):
        self._draw()

    def _draw(self):
        if self._df.empty:
            return

        amounts = self._df["amount"].tolist()

        p = self.plt
        p.clear_figure()
        p.hist(amounts, bins=50, color="blue")
        p.title("Transaction Amount Distribution")
        p.xlabel("Amount (€)")
        p.ylabel("Frequency")

    def refresh_data(self, df):
        self._df = df
        self._draw()
        self.refresh()
