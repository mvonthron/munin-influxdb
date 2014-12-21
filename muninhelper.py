
from collections import defaultdict
import os
import stat
import subprocess
import xml.etree.ElementTree as ET


CONFIG_KEYWORDS = [
    'host_name',
    'multigraph',
]


class PluginConfig:
    graph = {
        'title': '',
        'info': '',
        'category': '',
        'vlabel': '',
        'order': '',
    }
    hostname = ""
    is_multigraph = False
    fields = None
    expected_filename = None

def parse_plugin_config(name, text):
    config = PluginConfig()
    config.fields = defaultdict(dict)

    for line in text:
        if len(line) < 1:
            continue
        # remove # for comments
        if line.find('#') >= 0:
            line = line[:line.find('#')]
        else:
            line = line.strip(" \n")

        elements = line.split(" ")
        key, value = elements[0], elements[1:]

        if key.startswith("graph_"):
            key = key[len("graph_"):]
            if key in config.graph:
                config.graph[key] = " ".join(value)

        elif key in CONFIG_KEYWORDS:
            if key == "multigraph":
                raise Exception("Multigraph are not supported right now for automatic dashboard but data will be imported and shown anyway")
            elif key == "host_name":
                config.hostname = " ".join(value)


        else:
            field = key.split(".")
            config.fields[field[0]][field[1]] = " ".join(value).strip()

    #rework fields
    for field in config.fields:
        for attribute, value in config.fields[field].items():
            #min:max values for warning/critical not yet supported
            if attribute == "warning":
                config.fields[field][attribute] = float(value.split(':')[0])
            if attribute == "critical":
                config.fields[field][attribute] = float(value.split(':')[0])
            if attribute == "min":
                config.fields[field][attribute] = float(value)
            if attribute == "line":
                value = value.split(':')
                config.fields[field][attribute] = {
                    'value': value[0],
                    'color': 'ff0000' if len(value) < 2 else value[1],
                    'label': None if len(value) < 3 else value[2]
                }
            if attribute == "type":
                config.fields[field][attribute] = value.lower()
            if attribute == "draw":
                config.fields[field][attribute] = value.lower()

        if not 'type' in config.fields[field]:
            config.fields[field]['type'] = 'gauge'

        config.expected_filename = "{0}-{1}-{2}.rrd".format(name, field, config.fields[field]['type'][0])
        return config

def retrieve_plugin_configs(folder):
    """

    """
    is_executable = lambda p: os.stat(os.path.join(folder, p))[stat.ST_MODE] & stat.S_IXUSR
    configurations = []
    plugins = os.listdir(folder)
    for plugin in plugins:
        if is_executable(plugin):
            try:
                stdout = subprocess.check_output(['munin-run', plugin, 'config'])
                c = parse_plugin_config(plugin, stdout.split('\n'))
                configurations.append(c)
            except Exception as e:
                print "Error reading {0} configuration, skipping.\n  Message: {1}".format(plugin, e.message)

        else:
            print "Not executable:", plugin

    return configurations




if __name__ == "__main__":
    with open("data/cpu.config") as f:
        parse_plugin_config('cpu', f.readlines())
