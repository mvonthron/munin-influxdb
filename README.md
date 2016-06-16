Munin-influxdb
==============

[Munin](http://munin-monitoring.org/) to [InfluxDB](http://influxdb.com)+[Grafana](http://grafana.org/) gateway

Tool to migrate smoothly from Munin (RRD) to InfluxDB and Grafana dashboards.

Provide two commands:

  * **import** 
    * Import existing Munin data to [InfluxDB](http://influxdb.com) (groups fields in the same series by default). *Status: done*
    * Generate a [Grafana](http://grafana.org/) dashboard based on the existing Munin configuration. *Status: done*
  * **fetch**
    * Update InfluxDB with fresh data from a still running Munin service: *Status: done*
    * Run Munin's plugins but export to InfluxDB instead. *Status: not started*

![Import](http://i.imgur.com/kjhlUTg.png)

### InfluxDB storage

Data from Munin RRD databases are combined and imported into an InfluxDB cluster (version 0.9 and later).

Munin fields from a same plugin are grouped as columns of the same InfluxDB time series.


### Grafana dashboard

Grafana layout settings are imported from Munin plugin's configuration. Supported elements:

  - Min, max, average and current values in legend table
  - Line, area, stacked metrics
  - Warning, critical thresholds
  - Graph orders
  - Aliases
  - Tooltip overlays
  - Metrics colors
  - Multigraphs (partial support)

![Dashboard](http://i.imgur.com/pddwXD4.png)

Installation
---------

Very simple!

1. Clone the repository:

    ```
    $ git clone https://github.com/mvonthron/munin-influxdb.git
    ``` 
    
2. Install as any Python package: 

  ```
  $ sudo python setup.py install
  ``` 
  
3. Run ```import``` command: 

  ```
  $ sudo ./muninflux import
  ```
  
4. A cron job will be automatically added after installation to refresh data from munin every 5 minutes (Munin default)

### Some more details

* About importing current data

* About fetching new data
 
Fresh data is not obtain from the RRD databases but from Munin's _storable_ files. This is a ![Perl specific format](http://perldoc.perl.org/Storable.html)
where Munin stores the two latest values for each metric.

// example of storable content

Licensing
---------

This program and its documentation are released under the terms of the
BSD license.

----
2016, Manuel Vonthron <manuel.vonthron@acadis.org>
