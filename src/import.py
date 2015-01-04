#!/usr/bin/env python

import munincache
from rrd import *
from influxdbclient import InfluxdbClient
from grafana import Dashboard
from utils import Color, Symbol
import json

def retrieve_munin_configuration():
    """
    """
    print "Exploring Munin structure"

    try:
        settings = munincache.discover_from_datafile(munincache.MUNIN_DATAFILE)
    except:
        print "  {0} Could not process datafile ({1}), will read www and RRD cache instead".format(Symbol.NOK_RED, munincache.MUNIN_DATAFILE)
        # read /var/cache/munin/www to check what's currently displayed on the dashboard
        settings = munincache.discover_from_www(munincache.MUNIN_WWW_FOLDER)
        settings = discover_from_rrd(MUNIN_RRD_FOLDER, settings=settings, insert_missing=False)
    else:
        print "  {0} Found {1}: extracted {2} measurement units".format(Symbol.OK_GREEN, munincache.MUNIN_DATAFILE, settings.nb_fields)

    #for each host, find the /var/lib/munin/<host> directory and check if node name and plugin conf match RRD files
    try:
        check_rrd_files(settings)
    except Exception as e:
        print "  {0} {1}".format(Symbol.NOK_RED, e.message)
    else:
        print "  {0} Found {1} RRD files".format(Symbol.OK_GREEN, settings.nb_rrd_files)

    return settings


def main():
    print "{0}Munin to InfluxDB migration tool{1}".format(Color.BOLD, Color.CLEAR)
    print "-"*20
    settings = retrieve_munin_configuration()

    #export RRD files as XML for (much) easier parsing
    #(but takes much more time)
    export_to_xml_new(settings, MUNIN_RRD_FOLDER)

    #reads every XML file and export as in the InfluxDB database
    exporter = InfluxdbClient(settings)
    exporter.prompt_setup()

    exporter.import_from_xml_folder(MUNIN_XML_FOLDER)
    print "{0} Munin data successfully imported to {1}/db/{2}".format(Symbol.OK_GREEN, exporter.host, exporter.db_name)

    # Generate a JSON file to be uploaded to Grafana
    print ""
    print "{0}Grafaba dashboard{1}".format(Color.BOLD, Color.CLEAR)
    create_dash = raw_input("Would you like to generate a Grafana dashboard? [y]/n") or "y"
    if create_dash in ("y", "Y"):
        dashboard = Dashboard("Munin dashboard")
        dashboard.prompt_setup(settings)
        dashboard.generate()

        try:
            dashboard.save()
        except Exception as e:
            print "{0} Could not write Grafana dashboard: {1}".format(Symbol.NOK_RED, e.message)
        else:
            print "{0} A Grafana dashboard has been successfully generated to {1}".format(Symbol.OK_GREEN, settings.grafana.filename)

if __name__ == "__main__":
    import traceback, sys
    try:
        main()
    except KeyboardInterrupt:
        print "\n{0} Canceled.".format(Symbol.NOK_RED)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        print "{0} Error: {1}".format(Symbol.NOK_RED, e.message)
