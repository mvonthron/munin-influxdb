#!/usr/bin/env python
import os
import sys

from vendor import storable

try:
    import watchdog
except ImportError:
    print "Please install python-watchdog to use this program in notify mode"
    print "  pip install watchdog"
    sys.exit(1)

def read_state_file(filename):
    data = storable.retrieve(filename)

def main():
    pass

if __name__ == "__main__":
    main()