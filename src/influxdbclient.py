import os
import getpass
import json
from collections import defaultdict

import influxdb
from utils import progress_bar, parse_handle, Color, Symbol
from rrd import read_xml_file


class InfluxdbClient:
    def __init__(self, settings, hostname="root@localhost:8086"):
        self.user, self.passwd, self.host, self.port, self.db_name = parse_handle(hostname)
        self.group_fields = True
        self.client = None
        self.valid = False

        self.settings = settings

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

        if self.db_name:
            self.client.switch_db(self.db_name)

    def test_db(self, name):
        assert self.client
        if not name:
            return False

        db_list = self.client.get_database_list()
        if not {'name': name} in db_list:
            create = raw_input("{0} database doesn't exist. Would you want to create it? [y]/n: ".format(name)) or "y"
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
            res = self.client.query('list series')
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

    def list_series(self):
        return self.client.get_list_series()

    def list_columns(self, series="/.*/"):
        """
        Return a list of existing series and columns in the database

        @param series: specific series or all by default
        @return: dict of series/columns: [{'name': 'series_name', 'columns': ['colA', 'colB']}]
        """
        res = self.client.query("select * from {0} limit 1".format(series))
        for series in res:
            del series['points']
            series['columns'].remove('time')
            series['columns'].remove('sequence_number')

        return res

    def prompt_setup(self):
        print "{0}Please enter InfluxDB connection information{1}".format(Color.BOLD, Color.CLEAR)
        while not self.client:
            hostname = raw_input("  - host/handle [{0}]: ".format(self.host)) or self.host

            self.user, self.passwd, self.host, self.port, self.db_name = parse_handle(hostname)
            if self.port is None:
                self.port = 8086

            # shortcut if everything is in the handle
            if self.connect(silent=True):
                break

            self.port = raw_input("  - port [{0}]: ".format(self.port)) or self.port
            self.user = raw_input("  - user [{0}]: ".format(self.user)) or self.user
            self.passwd = getpass.getpass("  - password: ")

            self.connect()

        while True:
            if self.db_name == "?":
                self.list_db()
            else:
                if self.test_db(self.db_name):
                    break
            self.db_name = raw_input("  - database [munin]: ") or "munin"

        group = raw_input("Group multiple fields of the same plugin in the same time series? [y]/n: ") or "y"
        self.group_fields = group in ("y", "Y")


    def upload_values(self, name, columns, points):
        if len(columns) != len(points[0]):
            raise Exception("Cannot insert in {0} series: expected {1} columns (contains {2})".format(name, len(columns), len(points)))

        body = [{
            "name": name,
            "columns": columns,
            "points": points,
        }]

        try:
            self.client.write_points(body)
        except influxdb.client.InfluxDBClientError as e:
            with open("/tmp/err-import-{0}.json".format(name), "w") as f:
                json.dump(body, f)
            raise Exception("Cannot insert in {0} series: {1}".format(name, e.message))


    def validate_record(self, name, columns):
        """
        Performs brief validation of the record made: checks that the named series exists
        contains the specified columns

        As InfluxDB doesn't store null values we cannot compare length for now
        """

        if not name in self.client.get_list_series():
            raise Exception("Series \"{0}\" doesn't exist")

        for column in columns:
            if column == "time":
                pass
            else:
                try:
                    res = self.client.query("select count({0}) from {1}".format(column, name))
                    assert res[0]['points'][0][1] >= 0
                except influxdb.client.InfluxDBClientError as e:
                    raise Exception(e.message)
                except Exception as e:
                    raise Exception("Column \"{0}\" doesn't exist. (May happen if original data contains only NaN entries)".format(column))

        return True

    def import_from_xml_folder(self, folder):
        # build file list and grouping if necessary
        file_list = os.listdir(folder)
        grouped_files = defaultdict(list)
        errors = []

        for file in file_list:
            parts = file.replace(".xml", "").split("-")
            series_name = ".".join(parts[0:-2])
            if self.group_fields:
                grouped_files[series_name].append((parts[-2], file))
            else:
                grouped_files[".".join([series_name, parts[-2]])].append(('value', file))

        show = raw_input("Would you like to see the prospective series and columns? y/[n]: ") or "n"
        if show in ("y", "Y"):
            for series_name in sorted(grouped_files):
                print "  - {2}{0}{3}: {1}".format(series_name, [name for name, _ in grouped_files[series_name]], Color.GREEN, Color.CLEAR)

        print "Importing {0} XML files".format(len(file_list))
        i = 0
        for series_name in grouped_files:
            data = []
            keys_name = ['time']
            values = defaultdict(list)
            for field, file in grouped_files[series_name]:
                i += 1
                progress_bar(i, len(file_list))

                keys_name.append(field)
                #@todo make read_xml_file yieldable
                content = read_xml_file(os.path.join(folder, file))
                [values[key].append(value) for key, value in content.items()]

            # join data with time as first column
            data.extend([[k]+v for k, v in values.items()])

            try:
                self.upload_values(series_name, keys_name, data)
            except Exception as e:
                errors.append(e.message)
                continue

            try:
                self.validate_record(series_name, keys_name)
            except Exception as e:
                errors.append("Validation error in {0}: {1}".format(series_name, e.message))

        if errors:
            print "The following errors were detected while importing:"
            for error in errors:
                print "  {0} {1}".format(Symbol.NOK_RED, error)

if __name__ == "__main__":
    # main used for dev/debug purpose only, use "import"
    e = InfluxdbClient()
    e.prompt_setup(None)
    e.import_from_xml_folder("/tmp/xml")