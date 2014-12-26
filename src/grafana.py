import json
import uuid
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
        self.alias = self.column

    def to_json(self):
        return {
            "function": self.func,
            "column": self.column,
            "series": self.series,
            "query": "select {0}({1}) from \"{2}\" where $timeFilter group by time($interval) order asc".format(self.func,
                                                                                                                self.column,
                                                                                                                self.series),
            "rawQuery": False,
            "alias": self.alias
        }

class Panel:
    def __init__(self, title="", series=None):
        self.title = title
        self.series = series
        self.queries = []
        self.datasource = None

    def add_query(self, column):
        query = Query(self.series, column)
        self.queries.append(query)
        return query

    def to_json(self):
        return {
            "title": self.title,
            "datasource": self.datasource,
            "type": "graph",
            "span": 12,
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
            "height": "250px",
            "panels": [panel.to_json() for panel in self.panels],
            "showTitle": len(self.title) > 0
        }


class Dashboard:
    def __init__(self, title):
        self.title = title
        self.rows = []
        self.tags = []
        self.datasource = None

    def add_row(self, title=""):
        row = Row(title)
        self.rows.append(row)
        return row

    def to_json(self):
        return {
            "id": None,
            "title": self.title,
            "tags": self.tags,
            "rows": [row.to_json() for row in self.rows],
            "time": {"from": "now-5d", "to": "now"},
        }

    @staticmethod
    def generate_simple(title, structure):
        """
        Generates a simple dashboard based on the
        @return:
        """
        dashboard = Dashboard(title)

        for series in structure:
            row = dashboard.add_row()
            panel = row.add_panel(series['name'].split(".")[-1], series['name'])

            for col in series['columns']:
                panel.add_query(col)

        return dashboard.to_json()

if __name__ == "__main__":
    # main for dev/debug purpose only
    """
    dashboard = Dashboard("Munin")
    dashboard.tags.append("munin")
    dashboard.datasource = "munin"

    row = dashboard.add_row("Tesla")
    panel = row.add_panel("Memory", series="acadis.org.tesla.memory")
    panel.datasource = dashboard.datasource

    for field in ["apps", "free", "slab", "buffers"]:
        panel.add_query(field)

    # pprint(dashboard.to_json())

    print json.dumps(dashboard.to_json(),indent=2, separators=(',', ': '))
    """

    import influxdbclient
    client = influxdbclient.InfluxdbClient("...")
    client.connect()

    dashboard = Dashboard.generate_simple("Munin", client.list_columns())
    with open("/tmp/munin-grafana.json", "w") as f:
        json.dump(dashboard, f, indent=2, separators=(',', ': '))

    