from collections import defaultdict
import os
import pprint
import json

from utils import parse_handle

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

class Defaults:
    MUNIN_RRD_FOLDER = "/var/lib/munin/"
    MUNIN_XML_FOLDER = "/tmp/xml"
    DEFAULT_RRD_INDEX = 42

    MUNIN_WWW_FOLDER = "/var/cache/munin/www"
    MUNIN_VAR_FOLDER = "/var/lib/munin"
    MUNIN_DATAFILE = "/var/lib/munin/datafile"

class Settings:
    def __init__(self, cli_args):
        self.domains = defaultdict(Domain)

        self.interactive = cli_args.interactive
        self.verbose = cli_args.verbose

        self.influxdb = parse_handle(cli_args.influxdb)
        self.influxdb.update({
            "group_fields": cli_args.group_fields,
        })
        self.paths = {
            "munin": cli_args.munin_path,
            "datafile": os.path.join(cli_args.munin_path, 'datafile'),
            "www": cli_args.www,
            "xml": cli_args.xml_temp_path,
        }
        self.grafana = {
            "create": cli_args.grafana,
            "filename": cli_args.grafana_file,
            "title": cli_args.grafana_title,
            "graph_per_row": cli_args.grafana_cols,
            "tags": cli_args.grafana_tags,
            "show_minmax": cli_args.show_minmax,
        }

        self.nb_plugins = 0
        self.nb_fields = 0
        self.nb_rrd_files = 0

    def save_fetch_config(self, filename):
        config = {
            "influxdb": self.influxdb,
            "statefiles": [os.path.join(self.paths['munin'], "state-{0}-{1}.storable".format(domain, host))
                           for domain in self.domains
                           for host in self.domains[domain].hosts
            ],
            # {rrd_filename: (series, column), ...}
            "metrics": {get_field(self, f, h, p, field).rrd_filename:
                                (get_field(self, f, h, p, field).influxdb_series,
                                 get_field(self, f, h, p, field).influxdb_column)
                       for f, h, p, field in self.iter_fields()
                       if get_field(self, f, h, p, field).xml_imported
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
