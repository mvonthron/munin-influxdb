#!/usr/bin/env python
import os
import sys

try:
    import storable
except ImportError:
    from vendor import storable

def read_state_file(filename):
    data = storable.retrieve(filename)

def main():
    pass

if __name__ == "__main__":
    main()