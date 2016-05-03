import os
import sys
import pprint

from utils import ProgressBar, Symbol
from settings import Settings

from vendor import storable

def discover_from_datafile(settings):
    """
    /var/lib/munin/htmlconf.storable contains a copy of all informations required to build the graph (limits, legend, types...)
    Parsing it should be much easier and much faster than running munin-run config

    @param filename: usually /var/lib/munin/datafile
    @return: settings
    """

    with open(settings.paths['datafile']) as f:
        for line in f.readlines():
            # header line
            if line.startswith("version"):
                continue
            else:
                line = line.strip()

            # ex: acadis.org;tesla:memory.swap.label swap
            domain, tail = line.split(";", 1)
            host, tail = tail.split(":", 1)
            head, value = tail.split(" ", 1)
            plugin_parts = head.split(".")
            plugin, field, property = ".".join(plugin_parts[0:-2]), plugin_parts[-2], plugin_parts[-1]
            # plugin name kept to allow running the plugin in fetch command
            plugin_name = plugin_parts[0]

            # if plugin.startswith("diskstats"):
            #     print head, plugin_parts, len(plugin_parts), value

            if len(plugin.strip()) == 0:
                # plugin properties
                settings.domains[domain].hosts[host].plugins[field].settings[property] = value
                settings.domains[domain].hosts[host].plugins[field].original_name = plugin_name
            else:
                # field properties
                settings.domains[domain].hosts[host].plugins[plugin].fields[field].settings[property] = value

    # post parsing
    for domain, host, plugin, field in settings.iter_fields():
        _field = settings.domains[domain].hosts[host].plugins[plugin].fields[field]
        settings.nb_fields += 1

        type_suffix = _field.settings["type"].lower()[0]
        _field.rrd_filename = os.path.join(settings.paths['munin'], domain, "{0}-{1}-{2}-{3}.rrd".format(host, plugin.replace(".", "-"), field, type_suffix))
        _field.xml_filename = os.path.join(settings.paths['xml'], "{0}-{1}-{2}-{3}-{4}.xml".format(domain, host, plugin.replace(".", "-"), field, type_suffix))

        # remove multigraph intermediates
        if '.' in plugin:
            mg_plugin, mg_field = plugin.split(".")
            if mg_plugin in settings.domains[domain].hosts[host].plugins \
                and mg_field in settings.domains[domain].hosts[host].plugins[mg_plugin].fields:

                del settings.domains[domain].hosts[host].plugins[mg_plugin].fields[mg_field]
                settings.nb_fields -= 1

    return settings

def discover_from_www(settings):
    """
    Builds a Munin dashboard structure (domain/host/plugins) by reading the HTML files
    rather than listing the cache folder because the later is likely to contain old data
    """

    # delayed  import since this function should not be used in the "normal" case
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        try:
            from BeautifulSoup import BeautifulSoup
        except ImportError:
            print "Please install BeautifulSoup to use this program"
            print "  pip install beautifulsoup4 or easy_install beautifulsoup4"
            sys.exit(1)

    folder = settings.paths['www']

    print "Reading Munin www cache: ({0})".format(folder)
    with open(os.path.join(folder, "index.html")) as f:
        root = BeautifulSoup(f.read())

    domains = root.findAll("span", {"class": "domain"})

    # hosts and domains are at the same level in the tree so let's open the file
    for domain in domains:
        with open(os.path.join(folder, domain.text, "index.html")) as f:
            domain_root = BeautifulSoup(f.read())

        links = domain_root.find(id="content").findAll("a")
        progress_bar = ProgressBar(len(links), title=domain.text)

        for link in links:
            progress_bar.update()

            elements = link.get("href").split("/")
            if len(elements) < 2 \
                or elements[0].startswith("..") \
                or elements[-1].startswith("index"):
                continue

            if len(elements) == 2:
                host, plugin = elements[0], elements[1]
            elif len(elements) == 3:
                # probably a multigraph, we'll be missing the plugin part
                # we won't bother reading the html file for now and guess it from the RRD database later
                host, plugin = elements[0], ".".join(elements[1:3])
            else:
                print "Unknown structure"
                continue

            plugin = plugin.replace(".html", "")
            settings.domains[domain.text].hosts[host].plugins[plugin].is_multigraph = (len(elements) == 3)
            settings.domains[domain.text].hosts[host].plugins[plugin].settings = {
                'graph_title': link.text,
            }
            settings.nb_plugins += 1

    return settings

def read_state_file(filename):
    assert filename.startswith("state") and filename.endswith("storable")

    try:
        data = storable.retrieve(filename)
    except Exception as e:
        print "{0} Error: could read state file {1}: {2}".format(Symbol.NOK_RED, filename, e.message)


if __name__ == "__main__":
    # main() for dev/debug only
    settings = discover_from_datafile("../data/datafile")
    # acadis.org;tesla:if_eth0.up.info
    pprint.pprint( dict(settings.domains["acadis.org"].hosts["house"].plugins["youtube_views_scilabus"].settings) )
    pprint.pprint( dict(settings.domains["acadis.org"].hosts["tesla"].plugins["if_eth0"].fields["up"].settings) )
