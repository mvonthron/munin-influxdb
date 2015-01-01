import json
from utils import progress_bar
from pprint import pprint
from settings import Settings

class Query:
    DEFAULT_FUNC = "mean"

    def __init__(self, series, column):
        self.func = Query.DEFAULT_FUNC
        self.series = series
        self.column = column
        self.alias = self.column

    def to_json(self, settings):
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
        self.fill = 0
        self.stack = False
        self.leftYAxisLabel = None
        self.overrides = []
        self.width = 6

    def add_query(self, column):
        query = Query(self.series, column)
        self.queries.append(query)
        return query

    def sort_queries(self, order):
        ordered_keys = order.split()
        self.queries.sort(key=lambda x: ordered_keys.index(x.column) if x.column in ordered_keys else len(self.queries))

    def process_graph_type(self, plugin):
        """
        Munin processes draw types on a per metric basis whereas Grafana sets the type for
        the whole panel. However overrides are possible since https://github.com/grafana/grafana/issues/425
        http://munin-monitoring.org/wiki/fieldname.draw
        """
        draw_list = [(field, plugin.fields[field].settings.get("draw", "LINE2")) for field in plugin.fields]
        hasStack = bool([x for x, y in draw_list if "STACK" in y])
        hasArea = bool([x for x, y in draw_list if "AREA" in y])

        if hasArea:
            self.fill = 5
        if hasArea:
            self.stack = True

        # build overrides list
        self.overrides = []
        for field, draw in draw_list:
            current = {"alias": field}
            # LINE* should be matched
            if hasArea and draw.startswith("LINE"):
                current["fill"] = 0
            # LINE* should be matched *but not* LINESTACK*
            if hasStack and draw.startswith("LINE") and not draw.startswith("LINESTACK"):
                current["stack"] = False

            if len(current) > 1:
                self.overrides.append(current)

    def to_json(self, settings):
        return {
            "title": self.title,
            "datasource": settings.influxdb.database,
            "stack": self.stack,
            "fill": self.fill,
            "type": "graph",
            "span": self.width,
            "targets": [query.to_json(settings) for query in self.queries],
            "tooltip": {
                "shared": len(self.queries) > 1,
                "value_type": "individual"
            },
            "legend": {
                "show": True,
                "values": True,
                "min": settings.grafana.show_minmax,
                "max": settings.grafana.show_minmax,
                "current": settings.grafana.show_minmax,
                "total": False,
                "avg": settings.grafana.show_minmax,
                "alignAsTable": settings.grafana.show_minmax,
                "rightSide": False
            },
            "seriesOverrides": self.overrides,
            "leftYAxisLabel": self.leftYAxisLabel,
        }

class HeaderPanel(Panel):
    def __init__(self, title):
        self.title = title
        self.content = ""
        self.series = None

    def to_json(self, _):
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

    def to_json(self, settings):
        self.panels.sort(key=lambda x: x.series)
        return {
            "title": self.title,
            "height": self.height,
            "panels": [panel.to_json(settings) for panel in self.panels],
            "showTitle": len(self.title) > 0
        }

class Dashboard:
    def __init__(self, title):
        self.title = title
        self.rows = []
        self.tags = []
        self.settings = Settings()

    def prompt_setup(self, settings=Settings()):
        self.settings = settings
        setup = self.settings.grafana

        setup.filename = raw_input("  Dashboard file destination [/tmp/munin-grafana.json]:").strip() or "/tmp/munin-grafana.json"

        graph_per_row = raw_input("  Number of graphs per row [2]:").strip() or "2"
        setup.graph_per_row = int(graph_per_row)

        show_minmax = raw_input("  Show min/max/current in legend [y]/n:").strip() or "y"
        setup.show_minmax = show_minmax in ("y", "Y")

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

    def to_json(self, settings):
        return {
            "id": None,
            "title": self.title,
            "tags": self.tags,
            "rows": [row.to_json(settings) for row in self.rows],
            "time": {"from": "now-5d", "to": "now"},
        }

    def save(self, filename=None):
        if filename is None:
            filename = self.settings.grafana.filename

        with open(filename, "w") as f:
            json.dump(self.to_json(self.settings), f)


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


    def generate(self):
        i = 0
        self.add_header(self.settings)

        for domain in self.settings.domains:
            for host in self.settings.domains[domain].hosts:
                row = self.add_row("{0} / {1}".format(domain, host))
                for plugin in self.settings.domains[domain].hosts[host].plugins:
                    _plugin = self.settings.domains[domain].hosts[host].plugins[plugin]
                    panel = row.add_panel(_plugin.settings["graph_title"] or plugin, ".".join([domain, host, plugin]))
                    panel.width = 12//self.settings.grafana.graph_per_row

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
                            if draw.startswith("LINE"):
                                pass

                        i += 1
                        progress_bar(i, self.settings.nb_rrd_files)

                    if "graph_vlabel" in _plugin.settings:
                        panel.leftYAxisLabel = _plugin.settings["graph_vlabel"].replace(
                            "${graph_period}",
                            _plugin.settings.get("graph_period", "second")
                        )

                    if "graph_order" in _plugin.settings:
                        panel.sort_queries(_plugin.settings["graph_order"])

                    panel.process_graph_type(_plugin)

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