Munin-influxdb
==============

[Munin](http://munin-monitoring.org/) to [InfluxDB](http://influxdb.com)+[Grafana](http://grafana.org/) gateway

Tool to migrate smoothly from Munin (RRD) to InfluxDB and Grafana dashboards.

Contains (*err, will contain*) two parts:

  * **import** 
    * Import existing Munin data to [InfluxDB](http://influxdb.com) (groups fields in the same series by default). *Status: almost done*
    * Generate a [Grafana](http://grafana.org/) dashboard based on the existing Munin configuration. *Status: almost done*
  * **collect**
    * Update InfluxDB with fresh data from a still running Munin service: *Status: not started*
    * Run Munin's plugins but export to InfluxDB instead. *Status: not started*

![Import](http://i.imgur.com/kjhlUTg.png)

### InfluxDB storage

Data from Munin RRD databases are combined and imported into an InfluxDB cluster.

Munin fields from a same plugin are grouped as columns of the same InfluxDB time series.


### Grafana dashboard

Grafana layout settings are imported from Munin plugin's configuration. Supported elements:

  - Min, max, average and current values in legend table
  - Line, area, stacked metrics
  - Warning, critical thresholds
  - Graph orders
  - Aliases
  - Tooltip overlays
  - Multigraphs (partial support)

![Dashboard](http://i.imgur.com/pddwXD4.png)

Licensing
---------

This program and its documentation are released under the terms of the
BSD license.

----
2014, Manuel Vonthron <manuel.vonthron@acadis.org>
