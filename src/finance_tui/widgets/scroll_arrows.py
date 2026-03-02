"""Panel drill-down message for overview panels."""

from textual.message import Message


class PanelDrillDown(Message):
    """Posted when Enter is pressed on a panel row."""

    def __init__(self, filter_query: str, panel_id: str = "", exclude: bool = False):
        super().__init__()
        self.filter_query = filter_query
        self.panel_id = panel_id
        self.exclude = exclude
