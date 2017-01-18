#!/usr/bin/env python
from __future__ import print_function

import argparse
import sys

from munininfluxdb import munin
from munininfluxdb import rrd
from munininfluxdb.settings import Settings, Defaults
from munininfluxdb.influxdbclient import InfluxdbClient
from munininfluxdb.grafana import Dashboard
from munininfluxdb.utils import Color, Symbol


def retrieve_munin_configuration(settings):
    """
    """
    print("Exploring Munin structure")

    try:
        settings = munin.discover_from_datafile(settings)
    except Exception as e:
        print("  {0} Could not process datafile ({1}), will read www and RRD cache instead".format(Symbol.NOK_RED, settings.paths['datafile']))

        # read /var/cache/munin/www to check what's currently displayed on the dashboard
        settings = munin.discover_from_www(settings)
        settings = rrd.discover_from_rrd(settings, insert_missing=False)
    else:
        print("  {0} Found {1}: extracted {2} measurement units".format(Symbol.OK_GREEN, settings.paths['datafile'],
                                                                        settings.nb_fields))

    # for each host, find the /var/lib/munin/<host> directory and check if node name and plugin conf match RRD files
    try:
        rrd.check_rrd_files(settings)
    except Exception as e:
        print("  {0} {1}".format(Symbol.NOK_RED, e))
    else:
        print("  {0} Found {1} RRD files".format(Symbol.OK_GREEN, settings.nb_rrd_files))

    return settings


def main(args):
    print("{0}Munin to InfluxDB migration tool{1}".format(Color.BOLD, Color.CLEAR))
    print("-" * 20)

    settings = Settings(args)
    settings = retrieve_munin_configuration(settings)

    # export RRD files as XML for (much) easier parsing (but takes much more time)
    print("\nExporting RRD databases:".format(settings.nb_rrd_files))
    nb_xml = rrd.export_to_xml(settings)
    print("  {0} Exported {1} RRD files to XML ({2})".format(Symbol.OK_GREEN, nb_xml, settings.paths['xml']))

    #reads every XML file and export as in the InfluxDB database
    exporter = InfluxdbClient(settings)
    if settings.interactive:
        exporter.prompt_setup()
    else:
        # even in non-interactive mode, we ask for the password if empty
        if not exporter.settings.influxdb['password']:
            exporter.settings.influxdb['password'] = InfluxdbClient.ask_password()
        exporter.connect()
        exporter.test_db(exporter.settings.influxdb['database'])    # needed to create db if missing

    exporter.import_from_xml()

    settings = exporter.get_settings()
    print("{0} Munin data successfully imported to {1}/db/{2}".format(Symbol.OK_GREEN, settings.influxdb['host'],
                                                                      settings.influxdb['database']))

    settings.save_fetch_config()
    print("{0} Configuration for 'munin-influxdb fetch' exported to {1}".format(Symbol.OK_GREEN,
                                                                                settings.paths['fetch_config']))

    # Generate a JSON file to be uploaded to Grafana
    print("\n{0}Grafaba dashboard{1}".format(Color.BOLD, Color.CLEAR))
    if not settings.influxdb['group_fields'] and settings.grafana['create']:
        print("%s Grafana dashboard generation is only supported in grouped fields mode.", Symbol.NOK_RED)
        return

    if settings.interactive:
        settings.grafana['create'] = (raw_input("Would you like to generate a Grafana dashboard? [y]/n: ") or "y") in ('y', 'Y')

    if settings.grafana['create']:
        dashboard = Dashboard(settings)
        if settings.interactive:
            dashboard.prompt_setup()

        dashboard.generate()

        if settings.grafana['host']:
            try:
                dash_url = dashboard.upload()
            except Exception as e:
                print("{0} Didn't quite work uploading: {1}".format(Symbol.NOK_RED, e))
            else:
                print("{0} A Grafana dashboard has been successfully uploaded to {1}".format(Symbol.OK_GREEN, dash_url))

        if settings.grafana['filename']:
            try:
                dashboard.save()
            except Exception as e:
                print("{0} Could not write Grafana dashboard: {1}".format(Symbol.NOK_RED, e))
            else:
                print("{0} A Grafana dashboard has been successfully generated to {1}".format(Symbol.OK_GREEN, settings.grafana['filename']))
    else:
        print("Then we're good! Have a nice day!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""
    'import' command is a conversion tool from Munin to InfluxDB + Grafana

    It reads Munin's configuration files, parses the RRD folder (WWW cache folder if needed) to extract the structure
    of your current Munin setup. Data, with full history, is converted to InfluxDB time series format and uploaded to
    a InfluxDB server. You then have the possibility to generate a Grafana dashboard (JSON file to be imported manually)
    taking advantage of the features of Grafana with you current Munin configuration and plugins.

    After 'import' is completed, a cron job is installed to run the 'fetch' command every 5 minutes (default Munin analysis
    period). This updates the InfluxDB series with fresh data from Munin.
    See 'fetch -h' for details.
    """)
    parser.add_argument('--interactive', dest='interactive', action='store_true')
    parser.add_argument('--no-interactive', dest='interactive', action='store_false')
    parser.set_defaults(interactive=True)
    parser.add_argument('--xml-temp-path', default=Defaults.MUNIN_XML_FOLDER,
                        help='set path where to store result of RRD exported files (default: %(default)s)')
    parser.add_argument('--keep-temp', action='store_true',
                        help='instruct to retain temporary files (mostly RRD\'s XML) after generation')
    parser.add_argument('-v', '--verbose', type=int, default=1,
                        help='set verbosity level (0: quiet, 1: default, 2: debug)')
    parser.add_argument('--fetch-config-path', default=Defaults.FETCH_CONFIG,
                        help='set output configuration file to be used but \'fetch\' command afterwards (default: %(default)s)')

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
    munargs.add_argument('--munin-path', default=Defaults.MUNIN_VAR_FOLDER,
                         help='path to main Munin folder (default: %(default)s)')
    munargs.add_argument('--www', '--munin-www-path', default=Defaults.MUNIN_WWW_FOLDER,
                         help='path to main Munin folder (default: %(default)s)')
    munargs.add_argument('--rrd', '--munin-rrd-path', default=Defaults.MUNIN_RRD_FOLDER,
                         help='path to main Munin folder (default: %(default)s)')

    # Grafana
    grafanargs = parser.add_argument_group('Grafana dashboard generation')
    grafanargs.add_argument('--grafana', dest='grafana', action='store_true',
                            help='enable Grafana dashboard generation (default)')
    grafanargs.add_argument('--no-grafana', dest='grafana', action='store_false',
                            help='disable Grafana dashboard generation')
    grafanargs.set_defaults(grafana=True)
    grafanargs.add_argument('--grafana-minmax', dest='show_minmax', action='store_true', help='display min/max/current in legend (default)')
    grafanargs.add_argument('--grafana-no-minmax', dest='show_minmax', action='store_false', help='no values in legend')
    grafanargs.set_defaults(show_minmax=True)
    grafanargs.add_argument('--grafana-title', default="Munin Dashboard", help='dashboard title')
    grafanargs.add_argument('--grafana-file', default="/tmp/munin-influxdb/munin-grafana.json",
                            help='path to output json file, will have to be imported manually to Grafana')
    grafanargs.add_argument('--grafana-cols', default=2, type=int, help='number of panel per row')
    grafanargs.add_argument('--grafana-tags', nargs='+', help='grafana dashboard tags')

    args = parser.parse_args()

    try:
        main(args)
    except KeyboardInterrupt:
        print("\n{0} Canceled.".format(Symbol.NOK_RED))
        sys.exit(1)
    except Exception as e:
        print("{0} Error: {1}".format(Symbol.NOK_RED, e))
        sys.exit(1)
