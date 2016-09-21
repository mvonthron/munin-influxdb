#!/usr/bin/env bash

function usage() {
    echo "usage:" $0 "<command> [<options>]"
    echo
    echo "Available commands:"
    echo "    import    Import data from an existing Munin setup to InfluxDB and (optionally) generate a Grafana dashboard"
    echo "    fetch     Update values in InfluxDB based on the previous import"
    echo "    help      Print this message"
}

function launch_install_cron() {
    python bin/fetch.py --install-cron $(dirname $(readlink -f "$0"))/bin/fetch.py
}

if [[ $1 == "import" ]]; then
    shift
    python bin/import.py $@ && launch_install_cron
elif [[ $1 == "fetch" ]]; then
    if [[ $2 == "--install-cron" ]]; then
        launch_install_cron
    else
        shift
        python bin/fetch.py $@
    fi
elif [[ $1 == "help" ]]; then
    usage
    exit 0
else
    usage
    exit 1
fi

