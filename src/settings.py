from collections import defaultdict

class Settings:
    structure = defaultdict(dict)
    total_len = 0

    class InfluxDB:
        host, port = "localhost", 8086
        user, passwd = "root", None
        database = "munin"

    class Grafana:
        generate = True
        output_file = None