#!/usr/bin/env python
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

        if name not in config['metrics']:
            age = (date - int(last_date)) // (24*3600)
            if age < 7:
                print "{0} Not found series {1} (updated {2} days ago)".format(Symbol.WARN_YELLOW, name, age)
            # otherwise very probably a removed plugin, no problem
            continue

        series, column = config['metrics'][name]

        data[series]['time'] = [last_date]
        data[series][column] = [last_value]

    return data


def read_state_file(filename):
    data = storable.retrieve(filename)
    assert 'spoolfetch' in data and 'value' in data
    return data['value'], data['spoolfetch']

def main():
    client = InfluxdbClient()

    config = None
    with open("/tmp/munin-collect-config.json") as f:
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
        client.upload_multiple_series(data)

        config['lastupdate'] = max(config['lastupdate'], int(values[1]))

    with open("/tmp/munin-collect-config.json", "w") as f:
        json.dump(config, f)
        print "{0} Updated configuration: {1}".format(Symbol.OK_GREEN, f.name)

if __name__ == "__main__":
    main()