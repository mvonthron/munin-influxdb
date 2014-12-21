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