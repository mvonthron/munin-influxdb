#!/usr/bin/env python
import os
import sys
import json
from collections import defaultdict

from utils import Symbol
from rrd import DEFAULT_RRD_INDEX
from influxdbclient import InfluxdbClient

try:
    import storable
except ImportError:
    from vendor import storable


def pack_values(config, values):
    suffix = ":{0}".format(DEFAULT_RRD_INDEX)
    metrics, date = values
    date = int(date)

    data = defaultdict(dict)
    for metric in metrics:

        (last_date, last_value), (previous_date, previous_value) = metrics[metric].values()

        # usually stored as rrd-filename:42 with 42 being a constant column name for RRD files
        if metric.endswith(suffix):
            name = metric[:-len(suffix)]
        else:
            name = metric

        if name in config['metrics']:
            series, column = config['metrics'][name]

            data[series]['time'] = [float(last_date)]
            data[series][column] = [float(last_value) if last_value != 'U' else None]   # 'U' is Munin value for unknown
        else:
            age = (date - int(last_date)) // (24*3600)
            if age < 7:
                print "{0} Not found series {1} (updated {2} days ago)".format(Symbol.WARN_YELLOW, name, age)
            # otherwise very probably a removed plugin, no problem

    return data


def read_state_file(filename):
    data = storable.retrieve(filename)
    assert 'spoolfetch' in data and 'value' in data
    return data['value'], data['spoolfetch']

def main(config_filename="/tmp/munin-fetch-config.json"):
    client = InfluxdbClient()

    config = None
    with open(config_filename) as f:
        config = json.load(f)
        print "{0} Opened configuration: {1}".format(Symbol.OK_GREEN, f.name)
    assert config

    client.settings.influxdb.update(config['influxdb'])
    assert client.connect()

    for statefile in config['statefiles']:
        try:
            values = read_state_file(statefile)

        except Exception as e:
            print "{0} Could not read state file {1}: {2}".format(Symbol.NOK_RED, statefile, e.message)
            continue
        else:
            print "{0} Parsed: {1}".format(Symbol.OK_GREEN, statefile)

        data = pack_values(config, values)
        if len(data):
            client.upload_multiple_series(data)
            config['lastupdate'] = max(config['lastupdate'], int(values[1]))
        else:
            print Symbol.NOK_RED, "No data found, is Munin still running?"

    with open(config_filename, "w") as f:
        json.dump(config, f)
        print "{0} Updated configuration: {1}".format(Symbol.OK_GREEN, f.name)

def install_cron(script_file):
    try:
        import crontab
    except ImportError:
        from vendor import crontab

    print "Installing cron job"

    cron = crontab.CronTab(user='root')
    job = cron.new(command=script_file, user='root', comment='Update InfluxDB with fresh values from Munin')
    job.minute.every(5)

    if job.is_valid() and job.is_enabled():
        cron.write()

    return job.is_valid() and job.is_enabled()

if __name__ == "__main__":
    if sys.argv[1] == "--install-cron":
        try:
            script_file = sys.argv[2]
        except IndexError:
            print "{0} {1} must be called with it's own path as second argument (the shell script does it for you).".format(Symbol.NOK_RED, sys.argv[0])
            sys.exit(1)

        install_cron(script_file)

    else:
        main()