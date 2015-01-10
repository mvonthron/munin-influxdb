#!/usr/bin/env python

import argparse

from munininfluxdb import munin
from munininfluxdb import rrd
from munininfluxdb.influxdbclient import InfluxdbClient
from munininfluxdb.grafana import Dashboard
from munininfluxdb.utils import Color, Symbol


def retrieve_munin_configuration():
    """
    """
    print "Exploring Munin structure"

    try:
        settings = munin.discover_from_datafile(munin.MUNIN_DATAFILE)
    except:
        print "  {0} Could not process datafile ({1}), will read www and RRD cache instead".format(Symbol.NOK_RED,
                                                                                                   munin.MUNIN_DATAFILE)
        # read /var/cache/munin/www to check what's currently displayed on the dashboard
        settings = munin.discover_from_www(munin.MUNIN_WWW_FOLDER)
        settings = rrd.discover_from_rrd(rrd.MUNIN_RRD_FOLDER, settings=settings, insert_missing=False)
    else:
        print "  {0} Found {1}: extracted {2} measurement units".format(Symbol.OK_GREEN, munin.MUNIN_DATAFILE,
                                                                        settings.nb_fields)

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
    print "-" * 20
    settings = retrieve_munin_configuration()

    # export RRD files as XML for (much) easier parsing (but takes much more time)
    print "\nExporting RRD databases:".format(settings.nb_rrd_files)
    nb_xml = rrd.export_to_xml(settings, rrd.MUNIN_RRD_FOLDER)
    print "  {0} Exported {1} RRD files to XML ({2})".format(Symbol.OK_GREEN, nb_xml, rrd.MUNIN_XML_FOLDER)

    #reads every XML file and export as in the InfluxDB database
    exporter = InfluxdbClient(settings)
    exporter.prompt_setup()

    exporter.import_from_xml()

    settings = exporter.get_settings()
    print "{0} Munin data successfully imported to {1}/db/{2}".format(Symbol.OK_GREEN, settings.influxdb['host'],
                                                                      settings.influxdb['database'])

    settings.save_fetch_config("/tmp/munin-fetch-config.json")
    print "{0} Configuration for 'munin-influxdb fetch' exported to {1}".format(Symbol.OK_GREEN,
                                                                                "/tmp/munin-fetch-config.json")

    # Generate a JSON file to be uploaded to Grafana
    print "\n{0}Grafaba dashboard{1}".format(Color.BOLD, Color.CLEAR)
    if not settings.influxdb['group_fields']:
        print Symbol.NOK_RED, "Grafana dashboard generation is only supported in grouped fields mode."
        return

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
            print "{0} A Grafana dashboard has been successfully generated to {1}".format(Symbol.OK_GREEN,
                                                                                          settings.grafana['filename'])
    else:
        print "Then we're good! Have a nice day!"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""
    'import' command
    """)
    parser.add_argument('--interactive', dest='interactive', action='store_true')
    parser.add_argument('--no-interactive', dest='interactive', action='store_false')
    parser.set_defaults(interactive=True)
    parser.add_argument('--keep-temp', action='store_true', help='instruct to retain temporary files (mostly RRD\'s XML) after generation')
    parser.add_argument('-v', '--verbose', type=int, default=1,
                        help='set verbosity level (0: quiet, 1: default, 2: debug)')
    parser.add_argument('--fetch-config-path', default='/tmp/munin-influxdb/fetch-config.json',
                        help='set output configuration file to be used but \'fetch\' command afterwards %(default)s)')
    # InfluxDB
    idbargs = parser.add_argument_group('InfluxDB parameters')
    idbargs.add_argument('-c', '--influxdb', default="root@localhost:8086/db/munin",
                        help='connection handle to InfluxDB server, format [user[:password]]@host[:port][/db/dbname] (default: %(default)s)')
    parser.add_argument('--group-fields', dest='group_fields', action='store_true',
                        help='group all fields of a plugin in the same InfluxDB time series (default)')
    parser.add_argument('--no-group-fields', dest='group_fields', action='store_false',
                        help='store each field in its own time series (cannot generate Grafana dashboard))')
    parser.set_defaults(group_fields=True)

    # Munin
    munargs = parser.add_argument_group('Munin parameters')
    munargs.add_argument('--munin-path', default="/var/lib/munin", help='path to main Munin folder (default: %(default)s)')
    munargs.add_argument('--www', '--munin-www-path', default="/var/cache/munin/www", help='path to main Munin folder (default: %(default)s)')
    munargs.add_argument('--rrd', '--munin-rrd-path', default="/var/lib/munin", help='path to main Munin folder (default: %(default)s)')

    # Grafana
    grafanargs = parser.add_argument_group('Grafana dashboard generation')
    grafanargs.add_argument('--grafana', dest='grafana', action='store_true', help='enable Grafana dashboard generation (default)')
    grafanargs.add_argument('--no-grafana', dest='grafana', action='store_false', help='disable Grafana dashboard generation')
    grafanargs.set_defaults(grafana=True)

    grafanargs.add_argument('--grafana-title', default="Munin Dashboard", help='dashboard title')
    grafanargs.add_argument('--grafana-file', default="/tmp/munin-influxdb/munin-grafana.json",
                            help='path to output json file, will have to be imported manually to Grafana')
    grafanargs.add_argument('--grafana-cols', default=2, type=int, help='number of panel per row')
    grafanargs.add_argument('--grafana-tags', nargs='+', help='grafana dashboard tags')

    args = parser.parse_args()

    import sys
    from pprint import pprint
    pprint(args)
    sys.exit(1)

    try:
        main()
    except KeyboardInterrupt:
        print "\n{0} Canceled.".format(Symbol.NOK_RED)
    except Exception as e:
        print "{0} Error: {1}".format(Symbol.NOK_RED, e.message)
