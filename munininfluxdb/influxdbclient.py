import os
import getpass
import json
from collections import defaultdict
from pprint import pprint

import influxdb
try:
    # poor man's check
    assert influxdb.__version__.startswith('2')
except (AssertionError, AttributeError) as e:
    raise ImportError("InfluxDB API is too old, please update (e.g: pip install influxdb --upgrade)")

import rrd
from utils import ProgressBar, parse_handle, Color, Symbol
from rrd import read_xml_file
from settings import Settings

class InfluxdbClient:
    def __init__(self, settings):
        self.client = None
        self.valid = False

        self.settings = settings

    def connect(self, silent=False):
        try:
            client = influxdb.InfluxDBClient(self.settings.influxdb['host'],
                                             self.settings.influxdb['port'],
                                             self.settings.influxdb['user'],
                                             self.settings.influxdb['password']
                                             )

            # dummy request to test connection
            client.get_list_database()
        except influxdb.client.InfluxDBClientError as e:
            self.client, self.valid = None, False
            if not silent:
                print "  {0} Could not connect to database: {1}".format(Symbol.WARN_YELLOW, e.message)
        except Exception as e:
            print "Error: ", e.message
            self.client, self.valid = None, False
        else:
            self.client, self.valid = client, True

        if self.settings.influxdb['database']:
            self.client.switch_database(self.settings.influxdb['database'])

        return self.valid

    def test_db(self, name):
        assert self.client
        if not name:
            return False

        db_list = self.client.get_list_database()
        if not {'name': name} in db_list:
            if self.settings.interactive:
                create = raw_input("{0} database doesn't exist. Would you want to create it? [y]/n: ".format(name)) or "y"
                if not create in ("y", "Y"):
                    return False

            try:
                self.client.create_database(name)
            except influxdb.client.InfluxDBClientError as e:
                print "Error: could not create database: ", e.message
                return False

        try:
            self.client.switch_database(name)
        except influxdb.client.InfluxDBClientError as e:
            print "Error: could not select database: ", e.message
            return False

        # dummy query to test db
        try:
            res = self.client.query('show series')
        except influxdb.client.InfluxDBClientError as e:
            print "Error: could not query database: ", e.message
            return False

        return True

    def list_db(self):
        assert self.client
        db_list = self.client.get_list_database()
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
        res = self.client.query("SELECT * FROM \"{0}\" LIMIT 1".format(series))
        for series in res:
            del series['points']
            series['columns'].remove('time')
            series['columns'].remove('sequence_number')

        return res

    @staticmethod
    def ask_password():
        return getpass.getpass("  - password: ")

    def prompt_setup(self):
        setup = self.settings.influxdb
        print "\n{0}InfluxDB: Please enter your connection information{1}".format(Color.BOLD, Color.CLEAR)
        while not self.client:
            hostname = raw_input("  - host/handle [{0}]: ".format(setup['host'])) or setup['host']

            # I miss pointers and explicit references :(
            setup.update(parse_handle(hostname))
            if setup['port'] is None:
                setup['port'] = 8086

            # shortcut if everything is in the handle
            if self.connect(silent=True):
                break

            setup['port'] = raw_input("  - port [{0}]: ".format(setup['port'])) or setup['port']
            setup['user'] = raw_input("  - user [{0}]: ".format(setup['user'])) or setup['user']
            setup['password'] = InfluxdbClient.ask_password()

            self.connect()

        while True:
            if setup['database'] == "?":
                self.list_db()
            else:
                if self.test_db(setup['database']):
                    break
            setup['database'] = raw_input("  - database [munin]: ") or "munin"

        group = raw_input("Group multiple fields of the same plugin in the same time series? [y]/n: ") or "y"
        setup['group_fields'] = group in ("y", "Y")

    def write_series(self, measurement, tags, fields, time_and_values):
        if len(fields) != len(time_and_values[0]):
            raise Exception("Cannot insert in {0} series: expected {1} columns (contains {2})".format(measurement, len(fields), len(time_and_values[0])))

        body = []
        for row in time_and_values:
            # InfluxDB does not accept null values (nor field-less entries)
            valid_fields = {field: val for field, val in zip(fields[1:], row[1:]) if val is not None}
            if valid_fields:
                body.append({
                    "measurement": measurement,
                    "tags": tags,
                    "time": row[0],
                    "fields": valid_fields
                })

        if body:
            try:
                self.client.write_points(body, time_precision='s')
            except influxdb.client.InfluxDBClientError as e:
                raise Exception("Cannot insert in {0} series: {1}".format(measurement, e.message))
        else:
            raise ValueError("Measurement {0} did not contain any non-null value".format(measurement))

    def validate_record(self, name, fields):
        """
        Performs brief validation of the record made: checks that the named series exists
        contains the specified columns

        As InfluxDB doesn't store null values we cannot compare length for now
        """

        if not len(self.client.query("SHOW MEASUREMENTS WITH MEASUREMENT=\"{0}\"".format(name))):
            raise Exception("Measurement \"{0}\" doesn't exist".format(name))

        for field in fields:
            if field == "time":
                pass
            else:
                try:
                    res = self.client.query("SELECT COUNT(\"{0}\") FROM \"{1}\"".format(field, name))
                    assert len(res) >= 0
                except influxdb.client.InfluxDBClientError as e:
                    raise Exception(e.message)
                except Exception as e:
                    raise Exception("Field \"{}\" in measurement {} doesn't exist. (May happen if original data contains only NaN entries)".format(field, name))

        return True

    def import_from_xml(self):
        print "\nUploading data to InfluxDB:"
        progress_bar = ProgressBar(self.settings.nb_rrd_files*3)  # nb_files * (read + upload + validate)
        errors = []

        def _upload_and_validate(measurement, tags, fields, packed_values):
            try:
                self.write_series(measurement, tags, fields, packed_values)
            except Exception as e:
                # print e
                errors.append((Symbol.NOK_RED, "Error writing {0} to InfluxDB: {1}".format(measurement, e.message)))
                return
            finally:
                progress_bar.update(len(fields)-1)  # 'time' column ignored

            try:
                self.validate_record(measurement, fields)
            except Exception as e:
                errors.append((Symbol.WARN_YELLOW, "Validation error in {0}: {1}".format(measurement, e.message)))
            finally:
                progress_bar.update(len(fields)-1)  # 'time' column ignored

        try:
            assert self.client and self.valid
        except:
            raise Exception("Not connected to a InfluxDB server")
        else:
            print "  {0} Connection to database \"{1}\" OK".format(Symbol.OK_GREEN, self.settings.influxdb['database'])

        if self.settings.influxdb['group_fields']:
            """
            In "group_fields" mode, all fields of a same plugin (ex: system, user, nice, idle... of CPU usage)
             will be represented as columns of the same time series in InfluxDB.

             Schema will be:
                +----------------------+-------+----------+----------+-----------+
                |   time_series_name   | col_0 |  col_1   |  col_2   | col_3 ... |
                +----------------------+-------+----------+----------+-----------+
                | domain.host.plugin   | time  | metric_1 | metric_2 | metric_3  |
                | acadis.org.tesla.cpu | time  | system   | user     | nice      |
                | ...                  |       |          |          |           |
                +----------------------+-------+----------+----------+-----------+
            """
            for domain, host, plugin in self.settings.iter_plugins():
                _plugin = self.settings.domains[domain].hosts[host].plugins[plugin]
                measurement = plugin
                tags = {
                    "domain": domain,
                    "host": host,
                    "plugin": plugin
                }
                if _plugin.is_multigraph:
                    tags["is_multigraph"] = True
                    print host, plugin

                field_names = ['time']
                values = defaultdict(list)
                values_with_time = []

                for field in _plugin.fields:
                    _field = _plugin.fields[field]

                    if _field.rrd_exported:
                        field_names.append(field)
                        try:
                            content = read_xml_file(_field.xml_filename)
                        except Exception as e:
                            errors.append((Symbol.WARN_YELLOW, "Could not read file for {0}: {1}".format(field, e.message)))
                        else:
                            [values[key].append(value) for key, value in content.items()]

                            # keep track of influxdb storage info to allow 'fetch'
                            _field.influxdb_measurement = measurement
                            _field.influxdb_field = field
                            _field.xml_imported = True

                    # update progress bar [######      ] 42 %
                    progress_bar.update()

                # join data with time as first column
                values_with_time.extend([[k]+v for k, v in values.items()])

                _upload_and_validate(measurement, tags, field_names, values_with_time)

        else:  # non grouping
            """
            In "non grouped" mode, all fields of a same plugin will have a dedicated time series and the values
             will be written to a 'value' column

             Schema will be:
                +-----------------------------+-------+-------+
                |      time_series_name       | col_0 | col_1 |
                +-----------------------------+-------+-------+
                | domain.host.plugin.metric_1 | time  | value |
                | domain.host.plugin.metric_2 | time  | value |
                | acadis.org.tesla.cpu.system | time  | value |
                | ...                         |       |       |
                +-----------------------------+-------+-------+
            """
            for domain, host, plugin, field in self.settings.iter_fields():
                _field = self.settings.domains[domain].hosts[host].plugins[plugin].fields[field]
                if not _field.rrd_exported:
                    continue
                measurement = field
                tags = {
                    "domain": domain,
                    "host": host,
                    "plugin": plugin
                }
                field_names = ['time', 'value']
                values = defaultdict(list)
                values_with_time = []

                _field.influxdb_measurement = measurement
                _field.influxdb_field = 'value'

                content = read_xml_file(_field.xml_filename)
                [values[key].append(value) for key, value in content.items()]
                _field.xml_imported = True
                progress_bar.update()

                # join data with time as first column
                values_with_time.extend([[k]+v for k, v in values.items()])
                _upload_and_validate(measurement, tags, field_names, values_with_time)

        for error in errors:
            print "  {} {}".format(error[0], error[1])

    def import_from_xml_folder(self, folder):
        raise DeprecationWarning

        # build file list and grouping if necessary
        file_list = os.listdir(folder)
        grouped_files = defaultdict(list)
        errors = []
        progress_bar = ProgressBar(len(file_list))

        for file in file_list:
            fullname = os.path.join(folder, file)
            parts = file.replace(".xml", "").split("-")
            series_name = ".".join(parts[0:-2])
            if self.settings.influxdb['group_fields']:
                grouped_files[series_name].append((parts[-2], fullname))
            else:
                grouped_files[".".join([series_name, parts[-2]])].append(('value', fullname))

        if self.settings.interactive:
            show = raw_input("Would you like to see the prospective series and columns? y/[n]: ") or "n"
            if show in ("y", "Y"):
                for series_name in sorted(grouped_files):
                    print "  - {2}{0}{3}: {1}".format(series_name, [name for name, _ in grouped_files[series_name]], Color.GREEN, Color.CLEAR)

        print "Importing {0} XML files".format(len(file_list))
        for series_name in grouped_files:
            data = []
            keys_name = ['time']
            values = defaultdict(list)
            for field, file in grouped_files[series_name]:
                progress_bar.update()

                keys_name.append(field)

                content = read_xml_file(file)
                [values[key].append(value) for key, value in content.items()]

            # join data with time as first column
            data.extend([[k]+v for k, v in values.items()])

            try:
                pass
                # self.upload_values(series_name, keys_name, data)
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

    def get_settings(self):
        # the getter is useless in theory but making it explicit enforces the idea that we made modifications
        return self.settings


if __name__ == "__main__":
    # main used for dev/debug purpose only, use "import"
    class MockSettings:
        influxdb = parse_handle("root@192.168.1.100:8086/db/munin")
        influxdb.update({"group_fields": True})

    e = InfluxdbClient(MockSettings())
    e.prompt_setup()
    # e.import_from_xml_folder("/tmp/xml")

