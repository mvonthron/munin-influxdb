import os
import errno
import subprocess
import math
from collections import defaultdict
import xml.etree.ElementTree as ET
from settings import Settings, Defaults
from utils import ProgressBar, Symbol


# RRD types
DATA_TYPES = {
    'a': 'ABSOLUTE',
    'c': 'COUNTER',
    'd': 'DERIVE',
    'g': 'GAUGE',
}


def read_xml_file(filename, keep_average_only=True, keep_null_values=True):
    values = defaultdict(dict)

    tree = ET.parse(filename)
    root = tree.getroot()

    last_update = int(root.find('lastupdate').text)
    step = int(root.find('step').text)

    if len(root.findall('ds')) > 1:
        print "  {0} Found more than one datasource in {1} which is not expected. Please report problem.".format(Symbol.NOK_RED, filename)

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
                if math.isnan(value) and keep_null_values:
                    value = None
                # we don't want to override existing values as they are 'fresher' and less likely to be averaged (CF'd)
                if not entry_date in values:
                    values[entry_date] = value

            except:
                value = None

            entry_date += entry_delta

    return values


def export_to_xml(settings):
    progress_bar = ProgressBar(settings.nb_rrd_files)

    try:
        os.makedirs(settings.paths['xml'])
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    for domain, host, plugin, field in settings.iter_fields():
        _field = settings.domains[domain].hosts[host].plugins[plugin].fields[field]

        if _field.rrd_found:
            progress_bar.update()

            code = subprocess.check_call(['rrdtool', 'dump', _field.rrd_filename, _field.xml_filename])
            if code == 0:
                _field.rrd_exported = True

    return progress_bar.current

def export_to_xml_in_folder(source, destination=Defaults.MUNIN_XML_FOLDER):
    """
    Calls "rrdtool dump" to convert RRD database files in "source" folder to XML representation
    Converts all *.rrd files in source folder
    """
    assert os.path.exists(source)
    try:
        os.makedirs(destination)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    filelist = [("", os.path.join(source, file)) for file in os.listdir(source) if file.endswith(".rrd")]
    nb_files = len(filelist)
    progress_bar = ProgressBar(nb_files)

    print "Exporting {0} RRD databases:".format(nb_files)

    for domain, file in filelist:
        src = os.path.join(source, domain, file)
        dst = os.path.join(destination, "{0}-{1}".format(domain, file).replace(".rrd", ".xml"))
        progress_bar.update()

        code = subprocess.check_call(['rrdtool', 'dump', src, dst])

    return nb_files


def discover_from_rrd(settings, insert_missing=True, print_missing=False):
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

    folder = settings.paths['munin']
    print "Reading Munin RRD cache: ({0})".format(folder)

    not_inserted = defaultdict(dict)

    for domain in os.listdir(folder):
        if not os.path.isdir(os.path.join(folder, domain)):
            #domains are represented as folders
            continue

        if not insert_missing and not domain in settings.domains:
            #skip unknown domains (probably no longer wanted)
            continue

        files = os.listdir(os.path.join(folder, domain))
        progress_bar = ProgressBar(len(files), title=domain)
        for filename in files:
            progress_bar.update()

            path = os.path.join(folder, domain, filename)
            if os.path.isdir(path) or not path.endswith(".rrd"):
                # not a RRD database
                continue

            parts = os.path.splitext(filename)[0].split('-')
            length = len(parts)

            if length < 4:
                print "Error:", filename, parts, length
                continue

            host, plugin, field, datatype = parts[0], ".".join(parts[1:-2]), parts[-2], parts[-1]

            if not insert_missing and (not host in settings.domains[domain].hosts or not plugin in settings.domains[domain].hosts[host].plugins):
                if not host in not_inserted[domain]:
                    not_inserted[domain][host] = set()
                not_inserted[domain][host].add(plugin)
                continue

            plugin_data = settings.domains[domain].hosts[host].plugins[plugin]
            try:
                assert os.path.exists(os.path.join(folder, domain, "{0}-{1}-{2}-{3}.rrd".format(host, plugin.replace(".", "-"), field, datatype[0])))
            except AssertionError:
                print "{0} != {1}-{2}-{3}-{4}.rrd".format(filename, host, plugin, field, datatype[0])
                plugin_data.fields[field].rrd_found = False
            else:
                plugin_data.fields[field].rrd_found = True
                plugin_data.fields[field].rrd_filename = os.path.join(settings.paths['munin'], domain, filename)
                plugin_data.fields[field].xml_filename = os.path.join(settings.paths['xml'], domain, filename.replace(".rrd", ".xml"))
                plugin_data.fields[field].settings = {
                    "type": DATA_TYPES[datatype]
                }
                settings.nb_fields += 1

    if print_missing and len(not_inserted):
        print "The following plugin databases were ignored"
        for domain, hosts in not_inserted.items():
            print "  - Domain {0}:".format(domain)
            for host, plugins in hosts.items():
                print "    {0} Host {1}: {2}".format(Symbol.NOK_RED, host, ", ".join(plugins))

    return settings


def check_rrd_files(settings, folder=Defaults.MUNIN_RRD_FOLDER):
    missing = []
    for domain, host, plugin, field in settings.iter_fields():
        _field = settings.domains[domain].hosts[host].plugins[plugin].fields[field]
        # print "{0}[{1}]: {2}".format(plugin, field, _field.rrd_filename)
        exists = os.path.exists(_field.rrd_filename)

        if not exists:
            _field.rrd_found = False
            missing.append(_field.rrd_filename)
        else:
            _field.rrd_found = True
            settings.nb_rrd_files += 1

    if len(missing):
        raise Exception("Not found in {0}:\n    - {1}".format(folder, "\n    - ".join(missing)))

