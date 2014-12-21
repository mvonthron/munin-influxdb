import os
from influxdb import InfluxDBClient
from utils import progress_bar
from rrdreader import read_xml_file

class Exporter:
    def __init__(self, host, user, passwd, db):
        self.host = host
        self.user = user
        self.passwd = passwd
        self.db = db
        self.group_fields = True

    def test_db(self):
        pass

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