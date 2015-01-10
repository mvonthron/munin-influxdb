#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='munin-influxdb',
    version='0.1',
    description='Munin to InfluxDB/Grafana gateway',
    author='Manuel Vonthron',
    author_email='manuel.vonthron@acadis.org',
    url='http://github.com/manuelvonthron/munin-influxdb',
    license='BSD',
    py_modules=['munininfluxdb'],
    install_requires=['influxdb>=0.1.12'],
    long_description=open('README.md').read(),
    packages=find_packages(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Topic :: System :: Monitoring',
    ]
)
