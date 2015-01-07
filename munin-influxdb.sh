#!/usr/bin/env bash

function usage() {
    echo "usage:" $0 "<command> [<options>]"
    echo
    echo "Available commands:"
    echo "    import    Import data from an existing Munin setup to InfluxDB and (optionally) generate a Grafana dashboard"
    echo "    fetch     Update values in InfluxDB based on the previous import"
    echo "    help      Print this message"
}


if [[ $1 == "import" ]]; then
    shift
    python src/import.py $@
elif [[ $1 == "fetch" ]]; then
    shift
    python src/fetch.py $@
elif [[ $1 == "help" ]]; then
    usage
    exit 0
else
    usage
    exit 1
fi

