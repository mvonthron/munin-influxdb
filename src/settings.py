from collections import defaultdict
import pprint

class Field:

    def __init__(self):
        self.settings = defaultdict(dict)
        self.name = None

        # RRD file
        self.rrd_filename = None
        self.rrd_database_found = None
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
    #old structure
    structure = defaultdict(dict)

    domains = defaultdict(Domain)

    total_len = 0

    class InfluxDB:
        host, port = "localhost", 8086
        user, passwd = "root", None
        database = "munin"

    class Grafana:
        generate = True
        output_file = None