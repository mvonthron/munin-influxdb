from pprint import pprint

try:
    import paramiko
except ImportError:
    print "SSH library Paramiko missing, needed for remote plugins"

class MuninRunner:
    def __init__(self):
        pass

class HostRunner:
    def __init__(self):
        pass


def main():
    content = {}

    with open("../data/munin-conf/munin.conf") as f:
        current_group = {}
        current_group_name = "_top_level_"

        for line in f.readlines():
            line = line.strip()
            # comment
            if line.startswith('#') or not line:
                pass

            # group
            elif line.startswith('['):
                # save old group
                content[current_group_name] = current_group

                # init new one
                line = line.strip('[]')
                splitted = line.split(';')
                if len(splitted) == 1:
                    domain_name = ".".join(line.split('.')[-2:])
                    host_name = line
                else:
                    domain_name, host_name = splitted

                current_group = {
                    'host': host_name,
                    'domain': domain_name
                }
                current_group_name = line

            # entry
            else:
                elements = line.split()
                if len(elements) > 2:
                    current_group[elements[0]] = elements[1:]
                else:
                    current_group[elements[0]] = elements[1]

    # save last one
    content[current_group_name] = current_group

    pprint(content)

if __name__ == "__main__":
    main()