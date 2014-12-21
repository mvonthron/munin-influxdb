from lxml import html
from pprint import pprint
import os

MUNIN_WWW_FOLDER = "/var/cache/munin/www"


def discover_from_www(folder):
    """
    Builds a Munin dashboard structure (domain/host/plugins) by reading the HTML files
    rather than listing the cache folder because the later is likely to contain old data
    """
    tree = html.parse(os.path.join(folder, "index.html"))
    root = tree.getroot()

    domains = root.find_class('domain')
    for domain in domains:
        domain_name = domain.text_content()
        domain_tree = html.parse(os.path.join(folder, domain_name, "index.html")).getroot()
        subdomains = domain_tree.xpath("[@class]")
        pprint(domain_tree)
        print "{0} domain has {1} hosts".format(domain_name, len(subdomains))

        for host in subdomains:
            print "Found host: ", host.text_content

            #multigraph
            multigraphs = domain_tree.findall('./domain')
            for m in multigraphs:
                print "Found multigraph: ", m.text_content()

    #pprint(root.find_class('host'))

if __name__ == "__main__":
    pprint(discover_from_www("data/www"))