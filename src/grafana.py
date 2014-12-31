import json
from utils import progress_bar
from pprint import pprint

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
            "alias": self.alias,
        }

class Panel:
    def __init__(self, title="", series=None):
        self.title = title
        self.series = series
        self.queries = []
        self.datasource = None
        self.fill = 0
        self.stack = False
        self.leftYAxisLabel = None

        self.width = 6

    def add_query(self, column):
        query = Query(self.series, column)
        self.queries.append(query)
        return query

    def sort_queries(self, order):
        ordered_keys = order.split()
        self.queries.sort(key=lambda x: ordered_keys.index(x.column) if x.column in ordered_keys else len(self.queries))

    def to_json(self):
        return {
            "title": self.title,
            "datasource": self.datasource,
            "stack": self.stack,
            "fill": self.fill,
            "type": "graph",
            "span": self.width,
            "targets": [query.to_json() for query in self.queries],
            "tooltip": {
                "shared": len(self.queries) > 1
            },
            "legend": {
                "show": True,
                "values": True,
                "min": True,
                "max": True,
                "current": True,
                "total": False,
                "avg": True,
                "alignAsTable": True,
                "rightSide": False
            },
            "leftYAxisLabel": self.leftYAxisLabel
        }

class HeaderPanel(Panel):
    def __init__(self, title):
        self.title = title
        self.content = ""

    def to_json(self):
        return {
            "title": self.title,
            "mode": "markdown",
            "type": "text",
            "editable": True,
            "span": 12,
            "links": [{
                "type": "absolute",
                "title": "Fork me on GitHub!",
                "url": "https://github.com/mvonthron/munin-influxdb",
            }],
            "content": self.content
        }

class Row:
    def __init__(self, title=""):
        self.title = title
        self.panels = []
        self.height = "250px"

    def add_panel(self, *args, **kwargs):
        p = Panel(*args, **kwargs)
        self.panels.append(p)
        return p

    def to_json(self):
        return {
            "title": self.title,
            "height": self.height,
            "panels": [panel.to_json() for panel in self.panels],
            "showTitle": len(self.title) > 0
        }

class Dashboard:
    def __init__(self, title):
        self.title = title
        self.rows = []
        self.tags = []
        self.datasource = None

        self.filename = "/tmp/munin-grafana.json"
        self.show_minmax = True
        self.graph_per_row = 2

    def prompt_setup(self):
        self.filename = raw_input("  Dashboard file destination [/tmp/munin-grafana.json]:").strip() or "/tmp/munin-grafana.json"

        graph_per_row = raw_input("  Number of graphs per row [2]:").strip() or "2"
        self.graph_per_row = int(graph_per_row)

        show_minmax = raw_input("   Show min/max/current in legend [y]/n:").strip() or "y"
        self.show_minmax = show_minmax in ("y", "Y")


    def add_header(self, settings):
        row = Row("")
        panel = HeaderPanel("Welcome")
        panel.content = \
"""
Thanks for using Munin-InfluxDB and the Grafana generator.

Don't forget to add the new database provider in Grafana's `settings.js` if
necessary:

    "dbname": {
        "type": "influxdb"
        "url": "http://localhost:8086/db/None",
        "username": "root",
        "password": "********",
    }
"""
        row.panels.append(panel)
        self.rows.append(row)

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

    def save(self, filename=None):
        if filename is None:
            filename = self.filename

        with open(filename, "w") as f:
            json.dump(self.to_json(), f)


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

        return dashboard


    def generate(self, settings):
        i = 0
        self.add_header(settings)

        for domain in settings.domains:
            for host in settings.domains[domain].hosts:
                row = self.add_row("{0} / {1}".format(domain, host))
                for plugin in settings.domains[domain].hosts[host].plugins:
                    _plugin = settings.domains[domain].hosts[host].plugins[plugin]
                    panel = row.add_panel(_plugin.settings["graph_title"] or plugin, ".".join([domain, host, plugin]))
                    panel.width = 12//self.graph_per_row

                    for field in _plugin.fields:
                        query = panel.add_query(field)

                        if "label" in _plugin.fields[field].settings:
                            query.alias = _plugin.fields[field].settings["label"]

                        if "draw" in _plugin.fields[field].settings:
                            draw = _plugin.fields[field].settings["draw"]
                            if draw == "AREA":
                                panel.fill = 5
                            if draw == "STACK":
                                panel.stack = True

                        i += 1
                        progress_bar(i, settings.nb_rrd_files)

                    if "graph_vlabel" in _plugin.settings:
                        panel.leftYAxisLabel = _plugin.settings["graph_vlabel"].replace(
                            "${graph_period}",
                            _plugin.settings.get("graph_period", "second")
                        )

                    if "graph_order" in _plugin.settings:
                        panel.sort_queries(_plugin.settings["graph_order"])


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

    # ---

    import influxdbclient
    client = influxdbclient.InfluxdbClient("...")
    client.connect()

    dashboard = Dashboard.generate_simple("Munin", client.list_columns())
    with open("/tmp/munin-grafana.json", "w") as f:
        json.dump(dashboard.to_json(), f, indent=2, separators=(',', ': '))
    """

    with open("../data/config.json") as f:
        conf = json.load(f)

    dashboard = Dashboard("Munin dashboard")
    dashboard.generate(conf)
    print json.dumps(dashboard.to_json(),indent=2, separators=(',', ': '))