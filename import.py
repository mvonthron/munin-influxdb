#!/usr/bin/env python

from muninwww import discover_from_www, MUNIN_WWW_FOLDER
from rrdreader import discover_from_rrd, export_xml_files, MUNIN_RRD_FOLDER, MUNIN_XML_FOLDER
from influxdbexport import InfluxdbClient
from utils import Color, Symbol

PLUGIN_DIR = "/etc/munin/plugins"
MUNIN_FOLDER = "data/acadis.org"
KEEP_AVERAGE_ONLY = True


def retrieve_munin_configuration():
    """
    """

    #run "munin-run * config" to get list of plugins and config
    #@todo takes too much time
    #plugins_conf = muninhelper.retrieve_plugin_configs(PLUGIN_DIR)

    #read /var/cache/munin/www to check what's currently displayed
    #on the dashboard
    config = discover_from_www(MUNIN_WWW_FOLDER)
    print ""

    #for each host, find the /var/lib/munin/<host> directory and check
    #if node name and plugin conf match RRD files
    #multigraphs? (diskstats)
    discover_from_rrd(MUNIN_RRD_FOLDER, structure=config, insert_missing=False)
    print ""

    return config


def main():
    print "{0}Munin to InfluxDB migration tool{1}".format(Color.BOLD, Color.CLEAR)
    print "-"*20
    config = retrieve_munin_configuration()

    #export RRD files as XML for (much) easier parsing
    #(but takes much more time)
    export_xml_files(MUNIN_RRD_FOLDER, config=config)

    #reads every XML file and export as in the InfluxDB database
    exporter = InfluxdbClient()
    exporter.prompt_setup()

    exporter.import_from_xml_folder(MUNIN_XML_FOLDER)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "\n{0} Canceled.".format(Symbol.NOK_RED)
    except Exception as e:
        print "{0} Error: {1}".format(Symbol.NOK_RED, e.message)