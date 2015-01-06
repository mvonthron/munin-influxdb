#!/usr/bin/env python

import munin
import rrd
from influxdbclient import InfluxdbClient
from grafana import Dashboard
from utils import Color, Symbol


def retrieve_munin_configuration():
    """
    """
    print "Exploring Munin structure"

    try:
        settings = munin.discover_from_datafile(munin.MUNIN_DATAFILE)
    except:
        print "  {0} Could not process datafile ({1}), will read www and RRD cache instead".format(Symbol.NOK_RED, munin.MUNIN_DATAFILE)
        # read /var/cache/munin/www to check what's currently displayed on the dashboard
        settings = munin.discover_from_www(munin.MUNIN_WWW_FOLDER)
        settings = rrd.discover_from_rrd(rrd.MUNIN_RRD_FOLDER, settings=settings, insert_missing=False)
    else:
        print "  {0} Found {1}: extracted {2} measurement units".format(Symbol.OK_GREEN, munin.MUNIN_DATAFILE, settings.nb_fields)

    # for each host, find the /var/lib/munin/<host> directory and check if node name and plugin conf match RRD files
    try:
        rrd.check_rrd_files(settings)
    except Exception as e:
        print "  {0} {1}".format(Symbol.NOK_RED, e.message)
    else:
        print "  {0} Found {1} RRD files".format(Symbol.OK_GREEN, settings.nb_rrd_files)

    return settings


def main():
    print "{0}Munin to InfluxDB migration tool{1}".format(Color.BOLD, Color.CLEAR)
    print "-"*20
    settings = retrieve_munin_configuration()

    #export RRD files as XML for (much) easier parsing (but takes much more time)
    print "\nExporting RRD databases:".format(settings.nb_rrd_files)
    nb_xml = rrd.export_to_xml(settings, rrd.MUNIN_RRD_FOLDER)
    print "  {0} Exported {1} RRD files to XML ({2})".format(Symbol.OK_GREEN, nb_xml, rrd.MUNIN_XML_FOLDER)

    #reads every XML file and export as in the InfluxDB database
    exporter = InfluxdbClient(settings)
    exporter.prompt_setup()

    exporter.import_from_xml()

    settings = exporter.get_settings()
    print "{0} Munin data successfully imported to {1}/db/{2}".format(Symbol.OK_GREEN, settings.influxdb['host'], settings.influxdb['database'])

    settings.save_collect_config("/tmp/munin-collect-config.json")
    print "{0} Configuration for 'munin-influxdb collect' exported to {1}".format(Symbol.OK_GREEN, "/tmp/munin-collect-config.json")

    # Generate a JSON file to be uploaded to Grafana
    print "\n{0}Grafaba dashboard{1}".format(Color.BOLD, Color.CLEAR)
    create_dash = raw_input("Would you like to generate a Grafana dashboard? [y]/n: ") or "y"
    if create_dash in ("y", "Y"):
        dashboard = Dashboard("Munin dashboard", settings)
        dashboard.prompt_setup()
        dashboard.generate()

        try:
            dashboard.save()
        except Exception as e:
            print "{0} Could not write Grafana dashboard: {1}".format(Symbol.NOK_RED, e.message)
        else:
            print "{0} A Grafana dashboard has been successfully generated to {1}".format(Symbol.OK_GREEN, settings.grafana['filename'])
    else:
        print "Then we're good! Have a nice day!"

if __name__ == "__main__":
    import traceback, sys
    try:
        main()
    except KeyboardInterrupt:
        print "\n{0} Canceled.".format(Symbol.NOK_RED)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        print "{0} Error: {1}".format(Symbol.NOK_RED, e.message)
