from collections import defaultdict
import pprint
import json

get_field = lambda s, d, h, p, f: s.domains[d].hosts[h].plugins[p].fields[f]

class Field:

    def __init__(self):
        self.settings = defaultdict(dict)
        #default values
        self.settings['type'] = "GAUGE"

        # RRD file
        self.rrd_filename = None
        self.rrd_found = None
        self.rrd_exported = None

        # XML
        self.xml_filename = None
        self.xml_imported = None

        # InfluxDB
        self.influxdb_series = None
        self.influxdb_column = None


class Plugin:
    def __init__(self):
        self.settings = defaultdict(dict)
        self.fields = defaultdict(Field)

        # is multigraph
        self.is_multigraph = False

    def __repr__(self):
        return pprint.pformat(dict(self.fields))

class Host:
    def __init__(self):
        self.plugins = defaultdict(Plugin)
        self.name = None

    def __repr__(self):
        return pprint.pformat(dict(self.plugins))


class Domain:
    def __init__(self):
        self.hosts = defaultdict(Host)
        self.name = None

    def __repr__(self):
        return pprint.pformat(dict(self.hosts))

class Settings:
    MUNIN_RRD_FOLDER = "/var/lib/munin/"
    MUNIN_XML_FOLDER = "/tmp/xml"
    DEFAULT_RRD_INDEX = 42

    MUNIN_WWW_FOLDER = "/var/cache/munin/www"
    MUNIN_VAR_FOLDER = "/var/lib/munin"
    MUNIN_DATAFILE = "/var/lib/munin/datafile"

    def __init__(self):
        self.domains = defaultdict(Domain)

    structure = defaultdict(dict)

    nb_plugins = 0
    nb_fields = 0
    nb_rrd_files = 0


    # reversed table to ease collect's job
    # reversed => [domain/host-plugin-field-t.rrd:42] = (series: domain.host.plugin, column: field)
    rrd_to_series = []

    class grafana:
        filename = "/tmp/munin-grafana.json"
        graph_per_row = 2
        show_minmax = True

    class influxdb:
        host, port = "localhost", 8086
        user, passwd = "root", None
        database = "munin"

    def save_collect_config(self, filename):
        config = {
            "connection": {
                "host": self.influxdb.host,
                "port": self.influxdb.port,
                "user": self.influxdb.user,
                "passwd": self.influxdb.passwd,
                "database": self.influxdb.database,
            },
            "statefiles": ["state-{0}-{1}.storable".format(domain, host) for domain in self.domains for host in self.domains[domain].hosts],
            "series": {get_field(self, f, h, p, field).rrd_filename: (get_field(self, f, h, p, field).influxdb_series, get_field(self, f, h, p, field).influxdb_column)
                       for f, h, p, field in self.iter_fields()
                       # if get_field(self, f, h, p, field).xml_imported
            },
            "lastupdate": None
        }

        with open(filename, "w") as f:
            json.dump(config, f, indent=2, separators=(',', ': '))

    def iter_plugins(self):
        """

        """
        for domain in self.domains:
            for host in self.domains[domain].hosts:
                for plugin in self.domains[domain].hosts[host].plugins:
                    yield domain, host, plugin


    def iter_fields(self):
        """

        """
        for domain in self.domains:
            for host in self.domains[domain].hosts:
                for plugin in self.domains[domain].hosts[host].plugins:
                    for field in self.domains[domain].hosts[host].plugins[plugin].fields:
                        yield domain, host, plugin, field
