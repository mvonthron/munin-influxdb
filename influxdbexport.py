import os
import influxdb
from utils import progress_bar, parse_handle
from rrdreader import read_xml_file

class Exporter:
    def __init__(self, hostname="root:root@localhost:8086"):
        self.user, self.passwd, self.host, self.port, self.db_name = parse_handle(hostname)

        self.group_fields = True

        self.client = None
        self.valid = False

    def connect(self):
        try:
            client = influxdb.InfluxDBClient(self.host, self.port, self.user, self.passwd)
            # dummy request to test connection
            client.get_database_list()
        except influxdb.client.InfluxDBClientError as e:
            self.client, self.valid = None, False
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

        return True

    def list_db(self):
        assert self.client
        l = self.client.get_database_list()

        print "List of existing databases:", l

    def prompt_setup(self):
        while not self.client:
            hostname = raw_input("Enter InfluxDB hostname? [{0}]: ".format(self.host)) or self.host
            self.user, self.passwd, self.host, self.port, self.db_name = parse_handle(hostname)
            if self.port is None:
                self.port = 8086

            # shortcut if everything in the handle
            if self.connect():
                break

            self.port = raw_input("Enter InfluxDB port? [{0}]: ".format(self.port)) or self.port
            self.user = raw_input("Enter InfluxDB user? [{0}]: ".format(self.user)) or self.user
            self.passwd = raw_input("Enter InfluxDB password? [{0}]: ".format(self.passwd)) or self.passwd

            self.connect()

        while True:
            if self.db_name == "?":
                self.list_db()
            else:
                if self.test_db(self.db_name):
                    break
            self.db_name = raw_input("Enter InfluxDB database name? [munin]: ") or "munin"

        group = raw_input("Group multiple fields of the same plugin in the same time series? [y]/n: ") or "y"
        self.group_fields = group in ("n", "N")


    def upload_values(self, name, values):
        pass

    def export_xml_from(self, folder):
        files = os.listdir(folder)

        print "Importing {0} XML files".format(len(files))
        i = 0
        for file in files:
            i += 1
            progress_bar(i, len(files))
            read_xml_file(os.path.join(folder, file))


if __name__ == "__main__":
    e = Exporter()
    e.prompt_setup()