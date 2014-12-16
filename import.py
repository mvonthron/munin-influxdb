#!/usr/bin/env python

import os
import datetime
from collections import defaultdict
import rrdtool
import re

MUNIN_FOLDER = "data/acadis.org"


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

    rra_index = set()
    ds_index = set()
    for line in infos:
        if line.startswith("rra"):
            match = re.findall(r'\d+', line)
            if len(match) > 0:
                rra_index.add(match[0])
        if line.startswith("ds"):
            match = re.findall(r'\d+', line)
            if len(match) > 0:
                ds_index.add(match[0])

    print rra_index, ds_index
    for i in range(rra_index):
        rra = defaultdict(dict)




def main():
    guessPluginListInFolder(MUNIN_FOLDER)

    readRRDFile(os.path.join(MUNIN_FOLDER, "house-youtube_subscribed_scilabus-count-g.rrd"))

if __name__ == "__main__":
    main()