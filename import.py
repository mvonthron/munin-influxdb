#!/usr/bin/env python

from datetime import datetime, timedelta
from collections import defaultdict

from muninwww import discover_from_www, MUNIN_WWW_FOLDER
from rrdreader import discover_from_rrd, export_xml_files, MUNIN_RRD_FOLDER, MUNIN_XML_FOLDER
from influxdbexport import Exporter

PLUGIN_DIR = "/etc/munin/plugins"
MUNIN_FOLDER = "data/acadis.org"
KEEP_AVERAGE_ONLY = True


def retrieve_munin_configuration():
    """
    """
    config = defaultdict(dict)

    #run "munin-run * config" to get list of plugins and config
    #@todo takes too much time
    #plugins_conf = muninhelper.retrieve_plugin_configs(PLUGIN_DIR)

    #read /var/cache/munin/www to check what's currently displayed
    #on the dashboard
    config = discover_from_www(MUNIN_WWW_FOLDER)

    #for each host, find the /var/lib/munin/<host> directory and check
    #if node name and plugin conf match RRD files
    #multigraphs? (diskstats)
    discover_from_rrd(MUNIN_RRD_FOLDER, structure=config, insert_missing=False)

    for host, value in config.items():
        print "---", host, "---"
        # pprint(dict(value))

    return config

def main():
    c = raw_input("Continue?")
    config = retrieve_munin_configuration()

    #export RRD files as XML for (much) easier parsing
    #(but takes much more time)
    # export_xml_files(MUNIN_RRD_FOLDER, config=config)

    #reads every XML file and export as in the InfluxDB database
    exporter = Exporter()
    exporter.prompt_setup()

    exporter.export_xml_from(MUNIN_XML_FOLDER)


if __name__ == "__main__":
    main()

