import os
import sys
from collections import defaultdict
from pprint import pprint

from utils import progress_bar


try:
    from bs4 import BeautifulSoup
except ImportError:
    try:
        from BeautifulSoup import BeautifulSoup
    except ImportError:
        print "Please install BeautifulSoup to use this program"
        print "  pip install beautifulsoup4 or easy_install beautifulsoup4"
        sys.exit(1)


MUNIN_WWW_FOLDER = "/var/cache/munin/www"


def discover_from_www(folder, structure=None):
    """
    Builds a Munin dashboard structure (domain/host/plugins) by reading the HTML files
    rather than listing the cache folder because the later is likely to contain old data
    """

    print "Reading Munin www cache: ({0})".format(folder)
    if structure is None:
        structure = defaultdict(dict)

    with open(os.path.join(folder, "index.html")) as f:
        root = BeautifulSoup(f.read())

    domains = root.findAll("span", {"class": "domain"})

    # hosts and domains are at the same level in the tree so let's open the file
    for domain in domains:
        structure[domain.text] = defaultdict(dict)

        with open(os.path.join(folder, domain.text, "index.html")) as f:
            domain_root = BeautifulSoup(f.read())

        links = domain_root.find(id="content").findAll("a")
        i=0
        for link in links:
            i += 1
            progress_bar(i, len(links), title=domain.text)

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
                host, plugin = elements[0], "-".join(elements[1:3])
            else:
                print "Unknown structure"
                continue

            structure[domain.text][host][plugin.replace(".html", "")] = {
                'title': link.text,
                'multigraph': True if len(elements) == 3 else False,
                'rrd_found': False,
                'fields': {}
            }

    return structure

if __name__ == "__main__":
    pprint(discover_from_www("data/www"))