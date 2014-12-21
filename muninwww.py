import os
from collections import defaultdict
from BeautifulSoup import BeautifulSoup
from pprint import pprint


MUNIN_WWW_FOLDER = "/var/cache/munin/www"


def discover_from_www(folder):
    """
    Builds a Munin dashboard structure (domain/host/plugins) by reading the HTML files
    rather than listing the cache folder because the later is likely to contain old data
    """
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
        for link in links:
            elements = link.get("href").split("/")
            if len(elements) < 2 \
                or elements[0].startswith("..") \
                or elements[1].startswith("index"):
                continue

            if len(elements) > 2:
                # probably a multigraph, we'll see later
                continue

            structure[domain.text][elements[0]][elements[1].replace(".html", "")] = link.text



        pprint(dict(structure[domain.text]))
    return structure

if __name__ == "__main__":
    pprint(discover_from_www("data/www"))