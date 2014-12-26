#!/usr/bin/env bash

function usage() {
    echo "usage:" $0 "command [options]"
}


if [[ $1 == "import" ]]; then
    shift
    python src/import.py $@
elif [[ $1 == "collect" ]]; then
    usage
    echo "Collect not implemented."
else
    usage
    exit 1
fi

