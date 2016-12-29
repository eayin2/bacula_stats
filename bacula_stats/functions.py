#!/usr/bin/python
# -*- coding: utf-8 -*-
import re
import os
import sys
import os
import logging
import traceback
from subprocess import Popen, PIPE
from collections import defaultdict

import fnmatch
import yaml
import psycopg2
from helputils.core import log
from six import iteritems
from voluptuous import Schema, Required, All, Length, Range, MultipleInvalid

logger = logging.getLogger(__name__)


def gb_to_tb(gb):
    return gb/(1000)


def client_fileset_size(dict):
    """Dict looks like: {'Full-ST': [(1,2,3), (2,3,4)], 'Incremental-ST': [(3,4,5), (4,5,6)] """
    tuple_list = list()
    gigabytes = float()
    for pk, pv in iteritems(dict):
        for t in pv:
            gigabytes += t[2]
    return "{0:.3f}".format(gigabytes/1024)


def validate_yaml():
    CONFIGPATH = "/etc/bacula_stats.conf"

    if not os.path.isfile(CONFIGPATH):
        log.error("Provide a /etc/bacula_stats.conf. Exiting.")
        sys.exit()
    with open((CONFIGPATH), "r") as stream:
        yaml_parsed = yaml.load(stream)
    schema = Schema({
        Required('bacula_config_path'): str,
        Required('port'): int,
        'timeouts': Schema({int: [str]})  # If timeouts not set, use default value.
    })
    try:
        schema(yaml_parsed)
    except MultipleInvalid as e:
        exc = e
        raise AssertionError(e)
    return yaml_parsed


yaml_parsed = validate_yaml()
bacula_config_path = yaml_parsed["bacula_config_path"]
port = str(yaml_parsed["port"])


def bacula_config_files():
    """Return all files found in bacula_config_path recursively. """
    files = []
    for root, dirnames, filenames in os.walk(bacula_config_path):
        for filename in fnmatch.filter(filenames, '*.conf'):
            file_path = os.path.join(root, filename)
            files.append(os.path.join(root, filename))
    return files


def config_values(d):
    """Try to get values for mulitple keys and set value None if key is not existent.

    Keys and values are packed and returned as dict.
    """
    d = {k.lower(): v for k, v in iteritems(d)}
    client = d.get("client", None)
    fileset = d.get("fileset", None)
    pool = d.get("pool", None)
    fbp = d.get("full backup pool", None)
    ibp = d.get("incremental backup pool", None)
    np = d.get("next pool", None)
    ty = d.get("type", None)
    cvl = {"client": client,
           "fileset": fileset,
           "pool": pool,
           "full backup pool": fbp,
           "incremental backup pool": ibp,
           "type": ty,
           "next pool": np}
    return cvl


def jobdefs_conf_values(jobdef_name):
    """Parse jobdefs.conf and return values for keys defined in config_values()."""
    files = bacula_config_files()
    for file in files:
        with open(file, "r") as myfile:
            parsed_conf = parse_bacula(myfile)
        if not parsed_conf:  # excludes nested configs, which our parser can't parse.
            continue
        for d in parsed_conf:
            if d["name"].lower() == jobdef_name and d["resource"].lower() == "jobdefs":
                jcd = config_values(d)
    return jcd   # job config dict


def parse_bacula(lines):
    """Parse bacula config and return a list of each config segment packed in one dictionary. """
    parsed = []
    obj = None
    for line in lines:
        line, hash, comment = line.partition('#')
        line = line.strip()
        if not line:
            continue
        m = re.match(r"(\w+)\s*{", line)
        if m:
            # Start a new object
            if obj is not None:
                # If file is nested skip it (eg filesets.conf is nested and we dont want to parse fileset resources).
                return None
            obj = {'resource': m.group(1)}
            parsed.append(obj)
            continue

        m = re.match(r"\s*}", line)
        if m:
            # End an object
            obj = None
            continue

        m = re.match(r"\s*([^=]+)\s*=\s*(.*)$", line)
        if m:
            # An attribute
            key, value = m.groups()
            obj[key.strip()] = value.rstrip(';')
            continue
    # Removing any quote signs from values and applying lower() to all keys.
    parsed = [{k.lower(): v.replace('"', "") for k, v in iteritems(dict)} for dict in parsed]
    return parsed


def client_pool_map():
    """Return two dicts, one of all pools a client is mapped to in bacula config and another with all copy pool deps."""
    files = bacula_config_files()
    jobs_config = defaultdict(lambda: defaultdict(set))
    config_copy_dep = defaultdict(set)
    for file in files:
        with open(file, "r") as myfile:
            parsed_conf = parse_bacula(myfile)
        if not parsed_conf:
            continue
        for d in parsed_conf:
            if d["resource"].lower() == "job":
                done = False
                d = {k.lower(): v for k, v in iteritems(d)}
                cvd = config_values(d)  # Config value dict
                if "jobdefs" in d:
                    # Besides creating jobs_config dictionary, create config_copy_dependency dictionary here.
                    jobdef_name = d["jobdefs"].lower()
                    jcd = jobdefs_conf_values(jobdef_name)  # Jobdefs config dict
                else:
                    # If no jobdefs then set jcd also to config values and when its compared to cvd then it doesnt
                    # differentiate from cvl.
                    jcd = config_values(d)
                cvd.update({jck: jcv for jck, jcv in iteritems(jcd) if jcv})
                # jobdefs config key (its just temp value dict, no nested things here)
                if cvd["fileset"] == None and cvd["type"].lower() == "copy" and cvd["next pool"]:  # Changed in may 2016
                    # to fix None in set (dict value), not sure if it fits in here though
                    # above we added also next pool (if available) to the dict cvd
                    config_copy_dep[d["pool"]].add(cvd["next pool"])
                    continue  # because we dont want fileset None-type in our jobs_config.
                elif (cvd["client"] == None or cvd["fileset"] == None or cvd["pool"] == None and not cvd['type'] ==
                      "copy"):
                    continue
                client, fileset = [cvd["client"], cvd["fileset"]]
                [jobs_config[client][fileset].add(pv)
                 for pv in [cvd["pool"], cvd["full backup pool"], cvd["incremental backup pool"]] if pv]
    return jobs_config, config_copy_dep  # Don't sort the dicts here yet, because we still need the set() values.


def hosts():
    """Searches for client resources, parses for address+name and then returns them as dict."""
    files = bacula_config_files()
    _hosts = defaultdict(lambda: defaultdict(list))
    for file in files:
        with open(file, "r") as myfile:
            parsed_conf = parse_bacula(myfile)
        if not parsed_conf:
            continue
        for d in parsed_conf:
            if d["resource"].lower() == "client" and d['address'] not in _hosts[d['name']]:
                _hosts[d['name']]["host"].append(d['address'])
    return _hosts


def host_up():
    """Checks if bacula's file daemon port is open and returns dictionary of available hosts.

    {
        "clientname": {
            "status": 0,
            "hosts": ["phlap01w", "phlap01e"]
        }
    }
    """
    _hosts = hosts()
    for ck, cv in iteritems(_hosts):
        for host in cv["host"]:
            p2 = Popen(["/usr/bin/netcat", "-z", "-v", "-w", "2", host, port], stdout=PIPE, stderr=PIPE,
                       universal_newlines=True)
            out, err = p2.communicate()
            if "succeeded" in err:
                _hosts[ck]["status"] = 1
                break
            else:
                _hosts[ck]["status"] = 0
    # _hosts = {k:list(v) for k, v in _hosts.items()}
    return _hosts
