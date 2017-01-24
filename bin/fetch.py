#!/usr/bin/env python
from __future__ import print_function
import pwd
import json
import os
import sys
import argparse
from collections import defaultdict

from munininfluxdb.utils import Symbol
from munininfluxdb.settings import Defaults

import influxdb

try:
    import storable
except ImportError:
    from vendor import storable

try:
    pwd.getpwnam('munin')
except KeyError:
    CRON_USER = 'root'
else:
    CRON_USER = 'munin'

# Cron job comment is used to uninstall and must not be manually deleted from the crontab
CRON_COMMENT = 'Update InfluxDB with fresh values from Munin'

def pack_values(config, values):
    suffix = ":{0}".format(Defaults.DEFAULT_RRD_INDEX)
    metrics, date = values
    date = int(date)

    data = defaultdict(dict)

    for metric in metrics:
        (latest_date, latest_value), (previous_date, previous_value) = metrics[metric].values()

        # usually stored as rrd-filename:42 with 42 being a constant column name for RRD files
        if metric.endswith(suffix):
            name = metric[:-len(suffix)]
        else:
            name = metric

        if name in config['metrics']:
            measurement, field = config['metrics'][name]

            data[measurement]['time'] = int(latest_date)
            data[measurement][field] = float(latest_value) if latest_value != 'U' else None   # 'U' is Munin value for unknown
        else:
            age = (date - int(latest_date)) // (24*3600)
            if age < 7:
                print("{0} Not found measurement {1} (updated {2} days ago)".format(Symbol.WARN_YELLOW, name, age))
            # otherwise very probably a removed plugin, no problem

    return [{
            "measurement": measurement,
            "tags": config['tags'][measurement],
            "time": fields['time'],
            "fields": {key: value for key, value in fields.iteritems() if key != 'time'}
        } for measurement, fields in data.iteritems()]

def read_state_file(filename):
    data = storable.retrieve(filename)
    assert 'spoolfetch' in data and 'value' in data
    return data['value'], data['spoolfetch']

def main(config_filename=Defaults.FETCH_CONFIG):
    config = None
    with open(config_filename) as f:
        config = json.load(f)
        print("{0} Opened configuration: {1}".format(Symbol.OK_GREEN, f.name))
    assert config

    client = influxdb.InfluxDBClient(config['influxdb']['host'],
                                     config['influxdb']['port'],
                                     config['influxdb']['user'],
                                     config['influxdb']['password']
                                     )
    try:
        client.get_list_database()
    except influxdb.client.InfluxDBClientError as e:
        print("  {0} Could not connect to database: {1}".format(Symbol.WARN_YELLOW, e))
        sys.exit(1)
    else:
        client.switch_database(config['influxdb']['database'])

    for statefile in config['statefiles']:
        try:
            values = read_state_file(statefile)

        except Exception as e:
            print("{0} Could not read state file {1}: {2}".format(Symbol.NOK_RED, statefile, e))
            continue
        else:
            print("{0} Parsed: {1}".format(Symbol.OK_GREEN, statefile))

        data = pack_values(config, values)
        if len(data):
            # print(data)
            try:
                client.write_points(data, time_precision='s')
            except influxdb.client.InfluxDBClientError as e:
                print("  {0} Could not write data to database: {1}".format(Symbol.WARN_YELLOW, e))
            else:
                config['lastupdate'] = max(config['lastupdate'], int(values[1]))
                print("{0} Successfully written {1} new measurements".format(Symbol.OK_GREEN, len(data)))
        else:
            print("%s No data found, is Munin still running?", Symbol.NOK_RED)

    with open(config_filename, "w") as f:
        json.dump(config, f)
        print("{0} Updated configuration: {1}".format(Symbol.OK_GREEN, f.name))

def uninstall_cron():
    if os.geteuid() != 0:
        print("It seems you are not root, please run \"muninflux fetch --uninstall-cron\" again with root privileges".format(sys.argv[0]))
        sys.exit(1)

    try:
        import crontab
    except ImportError:
        from vendor import crontab

    cron = crontab.CronTab(user=CRON_USER)
    jobs = list(cron.find_comment(CRON_COMMENT))
    cron.remove(*jobs)
    cron.write()

    return len(jobs)

def install_cron(script_file, period):
    if os.geteuid() != 0:
        print("It seems you are not root, please run \"muninflux fetch --install-cron\" again with root privileges".format(sys.argv[0]))
        sys.exit(1)

    try:
        import crontab
    except ImportError:
        from vendor import crontab

    cron = crontab.CronTab(user=CRON_USER)
    job = cron.new(command=script_file, user=CRON_USER, comment=CRON_COMMENT)
    job.minute.every(period)

    if job.is_valid() and job.is_enabled():
        cron.write()

    return job.is_valid() and job.is_enabled()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""
    'fetch' command grabs fresh data gathered by a still running Munin installation and send it to InfluxDB.

    Currently, Munin needs to be still running to update the data in '/var/lib/munin/state-*' files.
    """)
    parser.add_argument('--config', default=Defaults.FETCH_CONFIG,
                        help='overrides the default configuration file (default: %(default)s)')
    cronargs = parser.add_argument_group('cron job management')
    cronargs.add_argument('--install-cron', dest='script_path',
                        help='install a cron job to updated InfluxDB with fresh data from Munin every <period> minutes')
    cronargs.add_argument('-p', '--period', default=5, type=int,
                        help="sets the period in minutes between each fetch in the cron job (default: %(default)min)")
    cronargs.add_argument('--uninstall-cron', action='store_true',
                        help='uninstall the fetch cron job (any matching the initial comment actually)')
    args = parser.parse_args()

    if args.script_path:
        install_cron(args.script_path, args.period)
        print("{0} Cron job installed for user {1}".format(Symbol.OK_GREEN, CRON_USER))
    elif args.uninstall_cron:
        nb = uninstall_cron()
        if nb:
            print("{0} Cron job uninstalled for user {1} ({2} entries deleted)".format(Symbol.OK_GREEN, CRON_USER, nb))
        else:
            print("No matching job found (searching comment \"{1}\" in crontab for user {2})".format(Symbol.WARN_YELLOW,
                                                                                                     CRON_COMMENT, CRON_USER))
    else:
        main(args.config)
