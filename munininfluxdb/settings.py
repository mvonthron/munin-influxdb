from collections import defaultdict
import os
import pprint
import json
from os.path import expanduser

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
        self.influxdb_measurement = None
        self.influxdb_field = None


class Plugin:
    def __init__(self):
        self.settings = defaultdict(dict)
        self.fields = defaultdict(Field)

        # is multigraph
        self.is_multigraph = False
        self.original_name = ""

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
    MUNIN_RRD_FOLDER = "/var/lib/munin"
    MUNIN_VAR_FOLDER = "/var/lib/munin"
    MUNIN_WWW_FOLDER = "/var/cache/munin/www"
    MUNIN_DATAFILE = "/var/lib/munin/datafile"

    TEMP_FOLDER = "/tmp/munin-influxdb"
    FETCH_CONFIG = expanduser("~")+"/.config/munin-fetch-config.json"
    MUNIN_XML_FOLDER = TEMP_FOLDER+"/xml"

    DEFAULT_RRD_INDEX = 42

class Settings:
    def __init__(self, cli_args=None):
        self.domains = defaultdict(Domain)

        if cli_args:
            self.interactive = cli_args.interactive
            self.verbose = cli_args.verbose

            self.influxdb = parse_handle(cli_args.influxdb)
            self.influxdb.update({
                "group_fields": cli_args.group_fields,
            })
            self.paths = {
                "munin": cli_args.munin_path,
                "datafile": os.path.join(cli_args.munin_path, 'datafile'),
                "fetch_config": cli_args.fetch_config_path,
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
        else:
            self.interactive = True
            self.verbose = 1

            self.influxdb = parse_handle("root@localhost:8086/db/munin")
            self.influxdb.update({"group_fields": True})
            self.paths = {
                "munin": Defaults.MUNIN_VAR_FOLDER,
                "datafile": os.path.join(Defaults.MUNIN_VAR_FOLDER, 'datafile'),
                "fetch_config": Defaults.FETCH_CONFIG,
                "www": Defaults.MUNIN_WWW_FOLDER,
                "xml": Defaults.MUNIN_XML_FOLDER,
            }
            self.grafana = {
                "create": True,
                "filename": "/tmp/munin-influxdb/munin-grafana.json",
                "title": "Munin Dashboard",
                "graph_per_row": 2,
                "tags": "grafana munin",
                "show_minmax": True,
            }


        self.nb_plugins = 0
        self.nb_fields = 0
        self.nb_rrd_files = 0

    def save_fetch_config(self):
        config = {
            "influxdb": self.influxdb,
            "statefiles": [os.path.join(self.paths['munin'], "state-{0}-{1}.storable".format(domain, host))
                           for domain in self.domains
                           for host in self.domains[domain].hosts
            ],
            # {rrd_filename: (series, column), ...}
            "metrics": {get_field(self, d, h, p, field).rrd_filename:
                                (get_field(self, d, h, p, field).influxdb_measurement,
                                 get_field(self, d, h, p, field).influxdb_field)
                       for d, h, p, field in self.iter_fields()
                       if get_field(self, d, h, p, field).xml_imported
            },
            "tags": {get_field(self, d, h, p, field).influxdb_measurement: {"domain": d, "host": h,"plugin": p}
                       for d, h, p, field in self.iter_fields()
                       if get_field(self, d, h, p, field).xml_imported
            },
            "lastupdate": None
        }

        with open(self.paths['fetch_config'], 'w') as f:
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
