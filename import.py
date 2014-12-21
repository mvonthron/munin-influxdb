#!/usr/bin/env python

import os
from datetime import datetime, timedelta
from influxdb import InfluxDBClient
from pprint import pprint
from collections import defaultdict
from muninwww import discover_from_www, MUNIN_WWW_FOLDER
from rrdreader import discover_from_rrd, MUNIN_RRD_FOLDER

PLUGIN_DIR = "/etc/munin/plugins"
MUNIN_FOLDER = "data/acadis.org"
KEEP_AVERAGE_ONLY = True

def main():
    #guessPluginListInFolder(MUNIN_FOLDER)

    #readRRDFile(os.path.join(MUNIN_FOLDER, "house-youtube_subscribed_scilabus-count-g.rrd"))

    # cProfile.run("readRDDXML(os.path.join(MUNIN_FOLDER, 'xml', 'house-youtube_subscribed_scilabus-count-g.rrd.xml'))")
    combined_values = readRDDXML(os.path.join(MUNIN_FOLDER, "xml", "house-youtube_subscribed_scilabus-count-g.rrd.xml"))
    print "Got {0} entries total".format(len(combined_values))

    body = [{
        'name': 'test',
        'columns': ['time', 'value'],
        'points': [[x[0], x[1]] for x in combined_values.items()]
    }]

    client = InfluxDBClient('', 42, '', '', '')
    client.write_points(body)

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

    print ""
    for host, value in config.items():
        print "---", host, "---"
        pprint(dict(value))

if __name__ == "__main__":
    #main()
    retrieve_munin_configuration()

