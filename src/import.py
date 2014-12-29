#!/usr/bin/env python

from settings import Settings
from munincache import discover_from_www, MUNIN_WWW_FOLDER
from rrd import discover_from_rrd, export_to_xml, MUNIN_RRD_FOLDER, MUNIN_XML_FOLDER
from influxdbclient import InfluxdbClient
from grafana import Dashboard
from utils import Color, Symbol
import json

def retrieve_munin_configuration():
    """
    """
    settings = Settings()

    #run "munin-run * config" to get list of plugins and config
    #@todo takes too much time
    #plugins_conf = muninplugin.retrieve_plugin_configs(PLUGIN_DIR)

    #read /var/cache/munin/www to check what's currently displayed on the dashboard
    settings.structure = discover_from_www(MUNIN_WWW_FOLDER, settings.structure)
    print ""

    #for each host, find the /var/lib/munin/<host> directory and check if node name and plugin conf match RRD files
    discover_from_rrd(MUNIN_RRD_FOLDER, structure=settings.structure, insert_missing=False)
    print ""

    return settings


def main():
    print "{0}Munin to InfluxDB migration tool{1}".format(Color.BOLD, Color.CLEAR)
    print "-"*20
    settings = retrieve_munin_configuration()

    #export RRD files as XML for (much) easier parsing
    #(but takes much more time)
    export_to_xml(MUNIN_RRD_FOLDER, structure=settings.structure)

    #reads every XML file and export as in the InfluxDB database
    exporter = InfluxdbClient()
    exporter.prompt_setup()

    exporter.import_from_xml_folder(MUNIN_XML_FOLDER)
    print "{0} Munin data successfully imported to {1}/db/{2}".format(Symbol.OK_GREEN, exporter.host, exporter.db_name)

    # Generate a JSON file to be uploaded to Grafana
    print ""
    print "{0}Grafaba dashboard{1}".format(Color.BOLD, Color.CLEAR)
    create_dash = raw_input("Would you like to generate a Grafana dashboard? [y]/n") or "y"
    if create_dash in ("y", "Y"):
        filename = raw_input("  Dashboard file destination [/tmp/munin-grafana.json]:").strip() or "/tmp/munin-grafana.json"
        dashboard = Dashboard.generate("Munin dashboard", settings.structure)
        try:
            dashboard.save(filename)
        except Exception as e:
            print "{0} Could not write Grafana dashboard: {1}".format(Symbol.NOK_RED, e.message)
        else:
            print "{0} A Grafana dashboard has been successfully generated to {1}".format(Symbol.OK_GREEN, filename)
            print "  Don't forget to edit your Grafana config.js file to add the new data source:"
            print json.dumps({exporter.db_name: {
                "type": "influxdb", "url": "http://{0}:{1}/db/{2}".format(exporter.host, exporter.port, exporter.db_name),
                "username": exporter.user, "password": "<PASSWORD>"
            }}, indent=2, separators=(',', ': '))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "\n{0} Canceled.".format(Symbol.NOK_RED)
    except Exception as e:
        print "{0} Error: {1}".format(Symbol.NOK_RED, e.message)