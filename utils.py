import sys

def progress_bar(current, max, title="Progress", length=50):
    """
    from http://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console/13685020#13685020
    """
    percent = float(current) / max
    hashes = '#' * int(round(percent * length))
    spaces = ' ' * (length - len(hashes))
    sys.stdout.write("\r{0}: [{1}] {2}%".format(title, hashes + spaces, int(round(percent * 100))))
    sys.stdout.flush()
    if percent >= 1:
        print ""

def parse_handle(handle):
    e = handle.split('@')
    user = passwd = host = port = dbname = None

    def parse_dbname(dbname):
        elt = dbname.split("/")
        return elt[0], elt[-1] if len(elt) > 1 else None

    def parse_user(user):
        elt = user.split(":")
        return elt[0], elt[1] if len(elt) == 2 else None

    def parse_host(host):
        elt = host.split(":")
        if len(elt) == 1:
            port = None
            host, dbname = parse_dbname(elt[0])
        elif len(elt) == 2:
            host = elt[0]
            port, dbname = parse_dbname(elt[1])
        return host, port, dbname


    if len(e) == 2:
        user, passwd = parse_user(e[0])
    host, port, dbname =  parse_host(e[-1])

    return user, passwd, host, port, dbname