from pprint import pprint
import os
import getpass
import json
import influxdb
from utils import progress_bar, parse_handle, Color, Symbol
from rrdreader import read_xml_file
from collections import defaultdict

class InfluxdbClient:
    def __init__(self, hostname="root@localhost:8086"):
        self.user, self.passwd, self.host, self.port, self.db_name = parse_handle(hostname)
        self.group_fields = True
        self.client = None
        self.valid = False

    def connect(self, silent=False):
        try:
            client = influxdb.InfluxDBClient(self.host, self.port, self.user, self.passwd)
            # dummy request to test connection
            client.get_database_list()
        except influxdb.client.InfluxDBClientError as e:
            self.client, self.valid = None, False
            if not silent:
                print "Could not connect to database: ", e.message
        except Exception as e:
            print "Error: ", e.message
            self.client, self.valid = None, False
        else:
            self.client, self.valid = client, True

    def test_db(self, name):
        assert self.client
        if not name:
            return False

        db_list = self.client.get_database_list()
        if not {'name': name} in db_list:
            create = raw_input("{0} database doesn't exists. Would you want to create it? [y]/n: ".format(name)) or "y"
            if not create in ("y", "Y"):
                return False

            try:
                self.client.create_database(name)
            except influxdb.client.InfluxDBClientError as e:
                print "Error: could not create database: ", e.message
                return False

        try:
            self.client.switch_db(name)
        except influxdb.client.InfluxDBClientError as e:
            print "Error: could not select database: ", e.message
            return False

        # dummy query to test db
        try:
            res = self.client.query('select * from /.*/ limit 1;')
        except influxdb.client.InfluxDBClientError as e:
            print "Error: could not query database: ", e.message
            return False

        return True

    def list_db(self):
        assert self.client
        db_list = self.client.get_database_list()
        print "List of existing databases:"
        for db in db_list:
            print "  - {0}".format(db['name'])

    def prompt_setup(self):
        while not self.client:
            hostname = raw_input("Enter InfluxDB hostname? [{0}]: ".format(self.host)) or self.host
            self.user, self.passwd, self.host, self.port, self.db_name = parse_handle(hostname)
            if self.port is None:
                self.port = 8086

            # shortcut if everything is in the handle
            if self.connect(silent=True):
                break

            self.port = raw_input("Enter InfluxDB port? [{0}]: ".format(self.port)) or self.port
            self.user = raw_input("Enter InfluxDB user? [{0}]: ".format(self.user)) or self.user
            self.passwd = getpass.getpass("Enter InfluxDB password: ")

            self.connect()

        while True:
            if self.db_name == "?":
                self.list_db()
            else:
                if self.test_db(self.db_name):
                    break
            self.db_name = raw_input("Enter InfluxDB database name? [munin]: ") or "munin"

        group = raw_input("Group multiple fields of the same plugin in the same time series? [y]/n: ") or "y"
        self.group_fields = group in ("y", "Y")


    def upload_values(self, name, columns, points):
        body = [{
            "name": name,
            "columns": columns,
            "points": points,
        }]
        try:
            self.client.write_points(body)
        except Exception as e:
            print "Error writing to database:", e.message
            print name, pprint(columns)
            with open("/tmp/err-import-{0}.json".format(name), "w") as f:
                json.dump(body, f)
            return False
        else:
            return True

    def import_from_xml_folder(self, folder):
        # build file list and grouping if necessary
        file_list = os.listdir(folder)
        grouped_files = defaultdict(list)
        for file in file_list:
            parts = file.replace(".xml", "").split("-")
            series_name = ".".join(parts[0:-2])
            if self.group_fields:
                grouped_files[series_name].append((parts[-2], file))
            else:
                grouped_files[".".join([series_name, parts[-2]])].append(('value', file))

        show = raw_input("Would you like to see the prospective series and columns? y/[n]: ") or "n"
        if show in ("y", "Y"):
            for group in sorted(grouped_files):
                print "  - {2}{0}{3}: {1}".format(group, [name for name, _ in grouped_files[group]], Color.GREEN, Color.CLEAR)

        print "Importing {0} XML files".format(len(file_list))
        i = 0
        for group in grouped_files:
            data = []
            keys_name = ['time']
            values = defaultdict(list)
            for field, file in grouped_files[group]:
                i += 1
                progress_bar(i, len(file_list))

                keys_name.append(field)
                #@todo make read_xml_file yieldable
                content = read_xml_file(os.path.join(folder, file))
                [values[key].append(value) for key, value in content.items()]

            data.extend([[k]+v for k, v in values.items()])
            self.upload_values(group, keys_name, data)

if __name__ == "__main__":
    e = InfluxdbClient()
    e.prompt_setup()
    e.import_from_xml_folder("/tmp/xml")