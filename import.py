#!/usr/bin/env python

import os
from datetime import datetime, timedelta
from influxdb import InfluxDBClient


from collections import defaultdict
import rrdtool
import re
import math
import subprocess

import cProfile

import xml.etree.ElementTree as ET

MUNIN_FOLDER = "data/acadis.org"
KEEP_AVERAGE_ONLY = True

# Munin types
DATA_TYPES = {
    'a': 'absolute',
    'c': 'counter',
    'd': 'derivative',
    'g': 'absolute',
}

"""
http://munin-monitoring.org/wiki/MuninFileNames:
    /var/lib/munin/SomeGroup/foo.example.com-cpu-irq-d.rrd
               --------- --------------- --- --- -
                   |            |         |   |  `-- Data type (a = absolute, c = counter, d = derive, g = gauge)
                   |            |         |   `----- Field name / data source: 'irq'
                   |            |         `--------- Plugin name: 'cpu'
                   |            `------------------- Node name: 'foo.example.com'
                   `-------------------------------- Group name: 'SomeGroup'
"""
def guessPluginListInFolder(folder):
    nodes = defaultdict(dict)

    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)
        if os.path.isdir(path) or not path.endswith(".rrd"):
            continue

        parts = os.path.splitext(filename)[0].split('-')

        if(len < 4):
            print "Error:", filename, parts, len(parts)
            continue

        node, plugin, datatype = parts[0], parts[1], parts[-1]
        field = '-'.join(parts[2: -1])

        nodes[node][plugin] = {'field': field, 'type': DATA_TYPES[datatype], 'filename': filename}

def readRRDFile(filename):
    infos = rrdtool.info(filename)
    data = rrdtool.fetch(filename, 'MAX')

    lastupdate = datetime.datetime.fromtimestamp(int(infos['last_update']))
    step = int(infos["step"])
    print lastupdate
    print infos
    key0 = elements[0][0:elements[0].index('[')]
    key1 = elements[1][0:elements[1].index('[')]

    print key0, key1

    if key0 == "rra":
        rras[idx0][key1][idx1] = value

        if len(elements) > 2:
            print "That's new"
        else:
            item[line] = value

        if line.startswith("rra"):
            match = re.findall(r'\d+', line)
            if len(match) > 0:
                rra_index.add(match[0])
        if line.startswith("ds"):
            match = re.findall(r'\d+', line)
            if len(match) > 0:
                ds_index.add(match[0])

        print item

    print rras
    print rra_index, ds_index
    # for i in range(rra_index):
    #     rra = defaultdict(dict)


def readRDDXML(filename):
    print "Parsing XML file {0}".format(filename)
    values = defaultdict(dict)

    tree = ET.parse(filename)
    root = tree.getroot()

    last_update = int(root.find('lastupdate').text)
    step = int(root.find('step').text)

    for ds in root.findall('ds'):
        pass
        # print ds.find('name').text.strip()
        # print ds.find('type').text.strip()
        #
        # print ds.find('minimal_heartbeat').text.strip()
        # print ds.find('last_ds').text.strip()

    for rra in root.findall('rra'):
        if KEEP_AVERAGE_ONLY and rra.find('cf').text.strip() != "AVERAGE":
            # @todo store max and min in the same record but different column
            continue

        pdp_per_row = int(rra.find('pdp_per_row').text)
        entry_delta = pdp_per_row*step
        last_entry = last_update - last_update % entry_delta
        nb_entries = len(rra.find("database"))
        entry_date = first_entry = last_entry - (nb_entries-1)*entry_delta

        print "  + New segment from {0} to {1}. Nb entries: {2}. Granularity: {3} sec.".format(datetime.fromtimestamp(first_entry),
                                                                                               datetime.fromtimestamp(last_entry),
                                                                                               nb_entries,
                                                                                               entry_delta)

        # there should be only onv <v> entry per row, at least didn't see other cases with Munin
        for v in rra.findall("./database/row/v"):
            try:
                value = float(v.text)
                # we don't want to override existing values as they are 'fresher' and less likely to be averaged (CF'd)
                if math.isnan(value):
                    pass
                    #print entry_date, value
                elif not entry_date in values:
                    values[entry_date] = value

            except:
                value = None

            # if entry_date in values and values[entry_date] != value:
            #     #
            #     print " * {0} already has value {1}, new is {2} (probably averaged thus less precise)".format(datetime.fromtimestamp(entry_date),
            #                                                                                                   values[entry_date],
            #                                                                                                   value)

            entry_date += entry_delta

    return values


def main():
    #guessPluginListInFolder(MUNIN_FOLDER)

    #readRRDFile(os.path.join(MUNIN_FOLDER, "house-youtube_subscribed_scilabus-count-g.rrd"))

    # cProfile.run("readRDDXML(os.path.join(MUNIN_FOLDER, 'xml', 'house-youtube_subscribed_scilabus-count-g.rrd.xml'))")
    combined_values = readRDDXML(os.path.join(MUNIN_FOLDER, "xml", "house-youtube_subscribed_scilabus-count-g.rrd.xml"))
    print "Got {0} entries total".format(len(combined_values))

    body = [{
        'name': 'test',
        'columns': ['time', 'value'],
        'points': [ [x[0], x[1]] for x in combined_values.items()]
    }]

    client = InfluxDBClient('', 42, '', '', '')
    client.write_points(body)

def retrieveMuninConfiguration():
    """
    """
    config = defaultdict(dict)
    #read munin.conf to determine hostnames
    with open("data/munin-conf/munin.conf") as f:
        for line in f.readlines():
            if line.startswith('['):
                nodename = line.strip("[]\n").split(';')
                if len(nodename) == 1:
                   config[nodename] = {}
                elif len(nodename) == 2:
                    config[nodename[0]][nodename[1]] = {}
                else:
                    print "Doesn't sound right"
    
    #run "munin-run * config" to get list of plugins and config
    plugins = os.listdir("data/munin-conf/plugins")
    print plugins
    
    #for each host, find the /var/lib/munin/<host> directory and check 
    #if node name and plugin conf match RRD files
    for host in config:
        plugins = os.listdir("data/{0}".format(host))
    
    print config

if __name__ == "__main__":
    #main()
    retrieveMuninConfiguration()
