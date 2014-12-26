import json
from pprint import pprint

DASHBOARD_TEMPLATE = {
    "title": "template",
    "id": None,
    "tags": ["munin"],
    "timezone": "browser",

    "rows": []
}


class Query:
    DEFAULT_FUNC = "mean"

    def __init__(self, series, column):
        self.func = Query.DEFAULT_FUNC
        self.series = series
        self.column = column

    def to_json(self):
        return {
            "function": self.func,
            "column": self.column,
            "series": self.series,
            "query": "select {0}({1}) from \"{2}\" where $timeFilter group by time($interval) order asc".format(self.func,
                                                                                                                self.column,
                                                                                                                self.series),
            "rawQuery": False,
            "alias": self.column
        }

class Panel:
    def __init__(self, title="", series=None):
        self.title = title
        self.series = series
        self.queries = []

    def add_query(self, column):
        query = Query(self.series, column)
        self.queries.append(query)
        return query

    def to_json(self):
        return {
            "title": self.title,
            "targets": [query.to_json() for query in self.queries]
        }


class Row:
    def __init__(self, title=""):
        self.title = title
        self.panels = []

    def add_panel(self, *args, **kwargs):
        p = Panel(*args, **kwargs)
        self.panels.append(p)
        return p

    def to_json(self):
        return {
            "title": self.title,
            "panels": [panel.to_json() for panel in self.panels],
            "showTitle": len(self.title) > 0
        }

class Dashboard:
    def __init__(self):
        self.title = ""
        self.rows = []

    def add_row(self, title):
        row = Row(title)
        self.rows.append(row)
        return row

    def to_json(self):
        return {
            "id": None,
            "title": self.title,
            "rows": [row.to_json() for row in self.rows],
        }


if __name__ == "__main__":
    # main for dev/debug purpose only
    d = Dashboard()
    row = d.add_row("Tesla")
    panel = row.add_panel("Memory", series="acadis.org.tesla.memory")
    panel.add_query("buffers")

    pprint(d.to_json())