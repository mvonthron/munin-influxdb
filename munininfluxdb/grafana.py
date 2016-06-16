import json
import urlparse

from utils import ProgressBar, Color, Symbol
from pprint import pprint
from settings import Settings
from influxdbclient import InfluxdbClient

import requests

class Query:
    DEFAULT_FUNC = "mean"

    def __init__(self, measurement, field):
        self.func = Query.DEFAULT_FUNC
        self.measurement = measurement
        self.field = field
        self.alias = self.field

    def to_json(self, settings):
        return {
            "dsType": "influxdb",
            "measurement": self.measurement,
            "select": [[
                {"params": [self.field], "type": "field"},
                {"params": [], "type": self.func}
            ]],
            "groupBy": [
                {"params": ["$interval"], "type": "time"},
                {"params": ["null"], "type": "fill"}
            ],
            "resultFormat": "time_series",
            "alias": self.alias
        }

class Panel:
    def __init__(self, title="", measurement=None):
        self.title = title
        self.measurement = measurement
        self.queries = []
        self.fill = 0
        self.stack = False
        self.leftYAxisLabel = None
        self.overrides = []
        self.alias_colors = {}
        self.thresholds = {}
        self.width = 6
        self.linewidth = 1

    def add_query(self, field):
        query = Query(self.measurement, field)
        self.queries.append(query)
        return query

    def sort_queries(self, order):
        ordered_keys = order.split()
        self.queries.sort(key=lambda x: ordered_keys.index(x.field) if x.field in ordered_keys else len(self.queries))

    def process_graph_settings(self, plugin_settings):
        if "graph_vlabel" in plugin_settings:
            self.leftYAxisLabel = plugin_settings["graph_vlabel"].replace(
                "${graph_period}",
                plugin_settings.get("graph_period", "second")
            )

        if "graph_order" in plugin_settings:
            self.sort_queries(plugin_settings["graph_order"])


    def process_graph_thresholds(self, fields):
        """
        @see http://munin-monitoring.org/wiki/fieldname.warning
        @see http://munin-monitoring.org/wiki/fieldname.critical
        """
        warnings = {fields[field].settings.get("warning") for field in fields if "warnings" in fields[field].settings}
        criticals = {fields[field].settings.get("critical") for field in fields if "critical" in fields[field].settings}

        if len(warnings) > 1 or len(criticals) > 1:
            # per-metric thresholds are not supported right now
            return

        if warnings or criticals:
            self.thresholds = {"thresholdLine": False}

        # format = min:max
        # min threshold not supported by Grafana :(
        if criticals:
            val = criticals.pop().split(":")
            if val[-1]:
                self.thresholds["threshold2"] = int(val[-1])
            # critical doesn't show up if warning is not set to something
            self.thresholds["threshold1"] = self.thresholds["threshold2"]

        if warnings:
            val = warnings.pop().split(":")
            if val[-1]:
                self.thresholds["threshold1"] = int(val[-1])


    def process_graph_types(self, fields):
        """
        Munin processes draw types on a per metric basis whereas Grafana sets the type for
        the whole panel. However overrides are possible since https://github.com/grafana/grafana/issues/425
        @see http://munin-monitoring.org/wiki/fieldname.draw
        """
        draw_list = [(field, fields[field].settings.get("draw", "LINE2")) for field in fields]
        hasStack = bool([x for x, y in draw_list if "STACK" in y])
        hasArea = bool([x for x, y in draw_list if "AREA" in y])

        if hasArea:
            self.fill = 5
            self.linewidth = 0
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
                current["linewidth"] = int(draw[-1])/2 # lines appear bigger on Grafana

            if len(current) > 1:
                self.overrides.append(current)

        # colors
        self.alias_colors = {field: '#'+fields[field].settings.get("colour") for field in fields if "colour" in fields[field].settings}

    def to_json(self, settings):
        return {
            "title": self.title,
            "datasource": settings.influxdb['database'],
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
                "min": settings.grafana['show_minmax'],
                "max": settings.grafana['show_minmax'],
                "current": settings.grafana['show_minmax'],
                "total": False,
                "avg": settings.grafana['show_minmax'],
                "alignAsTable": settings.grafana['show_minmax'],
                "rightSide": False
            },
            "xaxis": {
                "show": True
            },
            "yaxes":[
                {"format": "short", "label": None, "logBase": 1},
                {"format": "short", "label": None, "logBase": 1}
            ],
            "grid": self.thresholds,
            "seriesOverrides": self.overrides,
            "aliasColors": self.alias_colors,
            "leftYAxisLabel": self.leftYAxisLabel,
            "linewidth": self.linewidth,
        }

class HeaderPanel(Panel):
    def __init__(self, title):
        self.title = title
        self.content = ""
        self.measurement = None

    def to_json(self, _):
        return {
            "title": self.title,
            "mode": "html",
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
        self.panels.sort(key=lambda x: x.measurement)
        return {
            "title": self.title,
            "height": self.height,
            "panels": [panel.to_json(settings) for panel in self.panels],
            "showTitle": len(self.title) > 0
        }

class Dashboard:
    def __init__(self, settings):
        self.title = settings.grafana['title']
        self.tags = settings.grafana['tags']
        self.rows = []
        self.settings = settings

    def prompt_setup(self):
        setup = self.settings.grafana
        print "\nGrafana: Please enter your connection information"
        setup['host'] = raw_input("  - host [http://localhost:3000]: ").strip() or "http://localhost:3000"
        setup['auth'] = None
        setup['filename'] = None

        while not GrafanaApi.test_host(setup['host']) and not setup['filename']:
            print "\n{0}We couldn't connect to {1}, please try again or leave empty to save to a local file{2}".format(Symbol.WARN_YELLOW, setup['host'], Color.CLEAR)
            setup['host'] = raw_input("  - host: ").strip() or ""
            if not setup['host']:
                setup['filename'] = raw_input("  - local file [/tmp/munin-grafana.json]: ").strip() or "/tmp/munin-grafana.json"

        if GrafanaApi.test_host(setup['host']):
            while not GrafanaApi.test_auth(setup['host'], setup['auth']):
                user = raw_input("  - user [admin]: ").strip() or "admin"
                password = InfluxdbClient.ask_password()
                setup['auth'] = (user, password)

            setup['access'] = None
            while setup['access'] not in ("proxy", "direct"):
                setup['access'] = raw_input("  - data source access [proxy]/direct: ").strip() or "proxy"

        self.title = raw_input("  Dashboard title [{0}]: ".format(self.title)).strip() or self.title
        graph_per_row = raw_input("  Number of graphs per row [2]: ").strip() or "2"
        setup['graph_per_row'] = int(graph_per_row)

        show_minmax = raw_input("  Show min/max/current in legend [y]/n: ").strip() or "y"
        setup['show_minmax'] = show_minmax in ("y", "Y")

    def add_header(self, settings):
        row = Row("")
        panel = HeaderPanel("Welcome to your new dashboard!")
        content = \
'''
<a href=\"https://github.com/mvonthron/munin-influxdb\"><img style=\"position: absolute; top: 0; right: 0; border: 0;\" src=\"https://camo.githubusercontent.com/365986a132ccd6a44c23a9169022c0b5c890c387/68747470733a2f2f73332e616d617a6f6e6177732e636f6d2f6769746875622f726962626f6e732f666f726b6d655f72696768745f7265645f6161303030302e706e67\" alt=\"Fork me on GitHub\" data-canonical-src =\"https://s3.amazonaws.com/github/ribbons/forkme_right_red_aa0000.png\"></a>

<p>Thanks for using Munin-InfluxDB and the Grafana generator.</p>

<ul>
<li>Edit the panels so they match your desires by clicking on their titles</li>
<li>You can remove this header through the green menu button on the top right corner of this panel</li>
<li>If all your panels show an "InfluxDB Error" sign, please check the datasource settings (here in Grafana)</li>
<li>Feel free to post your suggestions on the GitHub page</li>
</ul>
'''
        panel.content = content.format(**settings.influxdb)
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
            "timezone": "browser",
            "time": {"from": "now-5d", "to": "now"},
        }

    def save(self, filename=None):
        if filename is None:
            filename = self.settings.grafana['filename']

        with open(filename, "w") as f:
            json.dump(self.to_json(self.settings), f)

    def upload(self):
        api = GrafanaApi(self.settings)
        api.create_datasource(self.settings.influxdb['database'], self.settings.influxdb['database'])
        return api.create_dashboard(self.to_json(self.settings))

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

            for col in series['fields']:
                panel.add_query(col)

        return dashboard

    def generate(self):
        progress_bar = ProgressBar(self.settings.nb_rrd_files)

        self.add_header(self.settings)

        for domain in self.settings.domains:
            for host in self.settings.domains[domain].hosts:
                row = self.add_row("{0} / {1}".format(domain, host))
                for plugin in self.settings.domains[domain].hosts[host].plugins:
                    _plugin = self.settings.domains[domain].hosts[host].plugins[plugin]
                    panel = row.add_panel(_plugin.settings["graph_title"] or plugin, plugin)

                    for field in _plugin.fields:
                        query = panel.add_query(field)
                        if "label" in _plugin.fields[field].settings:
                            query.alias = _plugin.fields[field].settings["label"]
                        progress_bar.update()

                    panel.width = 12//self.settings.grafana['graph_per_row']
                    panel.process_graph_settings(_plugin.settings)
                    panel.process_graph_thresholds(_plugin.fields)
                    panel.process_graph_types(_plugin.fields)


class GrafanaApi:
    def __init__(self, config):
        # OAuth2 tokens not yet supported
        self.auth = config.grafana['auth']
        self.host = config.grafana['host'].rstrip('/')
        self.config = config

    @staticmethod
    def test_host(host):
        # should return "unauthorized"
        r = requests.get(host.rstrip("/") + "/api/org")
        return r.status_code == 401

    @staticmethod
    def test_auth(host, auth):
        r = requests.get(host.rstrip("/") + "/api/org", auth=auth)
        return r.status_code == 200

    def create_datasource(self, name, dbname):
        body = {
            "name": name,
            "database": dbname,
            "type": "influxdb",
            "url": "http://{0}:{1}".format(self.config.influxdb['host'].rstrip("/"), self.config.influxdb['port']),
            "user": self.config.influxdb['user'],
            "password": self.config.influxdb['password'],
            "access": self.config.grafana['access'],
            "basicAuth": False
        }
        r = requests.post(self.host + "/api/datasources", json=body, auth=self.auth)
        return r.ok

    def create_dashboard(self, dashboardJson):
        r = requests.post(self.host + "/api/dashboards/db", json={"dashboard": dashboardJson}, auth=self.auth)
        if r.ok:
            return "".join([self.host, "/dashboard/db/", r.json()['slug']])
        else:
            print r.json()
            r.raise_for_status()


if __name__ == "__main__":
    # main for dev/debug purpose only

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


    # with open("../data/config.json") as f:
    #     conf = json.load(f)
    #
    # dashboard = Dashboard("Munin dashboard")
    # dashboard.generate(conf)
    # print json.dumps(dashboard.to_json(),indent=2, separators=(',', ': '))