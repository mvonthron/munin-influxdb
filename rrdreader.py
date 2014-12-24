import os
from datetime import datetime
from collections import defaultdict
import subprocess
import math
import logging

import xml.etree.ElementTree as ET
from utils import progress_bar

MUNIN_RRD_FOLDER = "/var/lib/munin/"
MUNIN_XML_FOLDER = "/tmp/xml"

# RRD types
DATA_TYPES = {
    'a': 'absolute',
    'c': 'counter',
    'd': 'derive',
    'g': 'gauge',
}


def read_rrd_file(filename):
    import rrdtool

    infos = rrdtool.info(filename)
    data = rrdtool.fetch(filename, 'MAX')

    lastupdate = datetime.fromtimestamp(int(infos['last_update']))
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

def read_xml_file(filename, keep_average_only=True):
    # print "Parsing XML file {0}".format(filename)
    values = defaultdict(dict)

    tree = ET.parse(filename)
    root = tree.getroot()

    last_update = int(root.find('lastupdate').text)
    step = int(root.find('step').text)

    for ds in root.findall('ds'):
        pass

    for rra in root.findall('rra'):
        if keep_average_only and rra.find('cf').text.strip() != "AVERAGE":
            # @todo store max and min in the same record but different column
            continue

        pdp_per_row = int(rra.find('pdp_per_row').text)
        entry_delta = pdp_per_row*step
        last_entry = last_update - last_update % entry_delta
        nb_entries = len(rra.find("database"))
        entry_date = first_entry = last_entry - (nb_entries-1)*entry_delta

        # print "  + New segment from {0} to {1}. Nb entries: {2}. Granularity: {3} sec.".format(datetime.fromtimestamp(first_entry),
        #                                                                                        datetime.fromtimestamp(last_entry),
        #                                                                                        nb_entries,
        #                                                                                        entry_delta)

        # there should be only onv <v> entry per row, at least didn't see other cases with Munin
        for v in rra.findall("./database/row/v"):
            try:
                value = float(v.text)
                # we don't want to override existing values as they are 'fresher' and less likely to be averaged (CF'd)
                if math.isnan(value):
                    value = None
                    #print entry_date, value
                if not entry_date in values:
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

def export_xml_files(source, destination=MUNIN_XML_FOLDER, config=None):
    """

    """
    assert os.path.exists(source)
    try:
        os.makedirs(destination)
    except:
        pass

    if config is None:
        filelist = [("", os.path.join(source, file)) for file in os.listdir(source) if file.endswith(".rrd")]
    else:

        filelist = [(domain, attributes['filename'])
                    for domain, hosts in config.items()
                        for host, plugins in hosts.items()
                            for plugin, fields in plugins.items()
                                for field, attributes in fields['fields'].items()
                                    if fields['rrd_found']
        ]

    nb_files = len(filelist)
    print "Exporting {0} RRD databases:".format(nb_files)

    i = 0
    for domain, file in filelist:
        i += 1
        src = os.path.join(source, domain, file)
        dst = os.path.join(destination, "{0}-{1}".format(domain, file).replace(".rrd", ".xml"))
        progress_bar(i, nb_files)

        code = subprocess.check_call(['rrdtool', 'dump', src, dst])

    return nb_files


def discover_from_rrd(folder, structure=None, insert_missing=True, print_missing=False):
    """
    Builds a Munin dashboard structure (domain/host/plugins) by listing the files in the RRD folder

    http://munin-monitoring.org/wiki/MuninFileNames:
    /var/lib/munin/SomeGroup/foo.example.com-cpu-irq-d.rrd
               --------- --------------- --- --- -
                   |            |         |   |  `-- Data type (a = absolute, c = counter, d = derive, g = gauge)
                   |            |         |   `----- Field name / data source: 'irq'
                   |            |         `--------- Plugin name: 'cpu'
                   |            `------------------- Node name: 'foo.example.com'
                   `-------------------------------- Group name: 'SomeGroup'
    """

    print "Reading Munin RRD cache"

    if structure is None:
        structure = defaultdict(dict)
    not_inserted = defaultdict(dict)

    for domain in os.listdir(folder):
        if not os.path.isdir(os.path.join(folder, domain)):
            #domains are represented as folders
            continue

        if not insert_missing and not domain in structure:
            #skip unknown domains (probably no longer wanted)
            continue

        i = 0
        files = os.listdir(os.path.join(folder, domain))
        for filename in files:
            i += 1
            progress_bar(i, len(files), title=domain)

            path = os.path.join(folder, domain, filename)
            if os.path.isdir(path) or not path.endswith(".rrd"):
                # not a RRD database
                continue

            parts = os.path.splitext(filename)[0].split('-')
            length = len(parts)

            if(length < 4):
                print "Error:", filename, parts, length
                continue

            if length == 4:
                host, plugin, field, datatype = parts
            elif length == 5:
                host, plugin, field, datatype = parts[0], "-".join(parts[1:-2]), parts[-2], parts[-1]
            elif length > 5:
                print "Invalid:", parts
                continue
                # host, plugin, field, datatype = parts[0], parts[1], "_".join(parts[2:-1]), parts[-1]

            if not insert_missing and (not host in structure[domain] or not plugin in structure[domain][host]):
                if not host in not_inserted[domain]:
                    not_inserted[domain][host] = set()
                not_inserted[domain][host].add(plugin)
                continue

            plugin_data = structure[domain][host][plugin]
            try:
                assert os.path.exists(os.path.join(folder, domain, "{0}-{1}-{2}-{3}.rrd".format(host, plugin, field, datatype[0])))
            except AssertionError:
                print filename, "!=", "{0}-{1}-{2}-{3}.rrd".format(host, plugin, field, datatype[0])
            else:
                plugin_data["rrd_found"] = True
                plugin_data["fields"][field] = {'type': DATA_TYPES[datatype], 'filename': filename}

    if print_missing and len(not_inserted):
        print "The following plugin databases were ignored"
        for domain, hosts in not_inserted.items():
            print "  - Domain {0}:".format(domain)
            for host, plugins in hosts.items():
                print "    - Host {0}: {1}".format(host, ", ".join(plugins))

    return structure