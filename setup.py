#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='munin-influxdb',
    version='1.2.0',
    description='Munin to InfluxDB/Grafana gateway',
    author='Manuel Vonthron',
    author_email='manuel.vonthron@acadis.org',
    url='http://github.com/manuelvonthron/munin-influxdb',
    license='BSD',
    py_modules=['munininfluxdb'],
    install_requires=['influxdb>=2.12.0', 'requests'],
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Topic :: System :: Monitoring',
    ]
)
