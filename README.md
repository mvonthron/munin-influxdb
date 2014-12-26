Munin2influxdb
==============

[Munin](http://munin-monitoring.org/) to [InfluxDB](http://influxdb.com)+[Grafana](http://grafana.org/) gateway

Tool to migrate smoothly from Munin (RRD) to InfluxDB and Grafana dashboards.

Contains (*err, will contain*) two parts:
  * **import** 
    * Import existing Munin data to [InfluxDB](http://influxdb.com) (groups fields in the same series by default). *Status: almost done*
    * Generate a [Grafana](http://grafana.org/) dashboard based on the existing Munin configuration. *Status: coming soon*
  * **collect**
    * Run Munin's plugins but export to InfluxDB instead. *Status: not started*


Licensing
---------

This program and its documentation are released under the terms of the
BSD license.

----
2014, Manuel Vonthron <manuel.vonthron@acadis.org>
