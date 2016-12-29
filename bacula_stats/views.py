"""views.py"""
import datetime
import logging
import os
import re
import sys
from collections import defaultdict, OrderedDict
from subprocess import Popen, PIPE

import psycopg2
from helputils.core import format_exception
from six import iteritems

from .functions import client_pool_map, host_up, validate_yaml

logger = logging.getLogger(__name__)
# Validating YAML and retrieving timeout setting. if there's no timeout setting we use a default value here.
yaml_parsed = validate_yaml()
try:
    _timeouts = yaml_parsed["timeouts"]
except:
    # setting timeouts as integer. later our code checks whether _timeouts is a dict or integer.
    _timeouts = 30

recent_qry = ("""
    SELECT c.name, p.name, j.jobbytes, j.realendtime, j.starttime, j.jobfiles, f.fileset
    FROM client c
    LEFT JOIN (
        SELECT DISTINCT ON (j.clientid, j.poolid, j.filesetid)
        j.jobbytes, j.realendtime, j.clientid, j.poolid, j.starttime, j.jobfiles, j.type, j.level, j.jobstatus, j.filesetid
        FROM job j
        WHERE j.jobstatus IN ('T', 'W') AND j.level IN ('F', 'I', 'D') AND j.type IN ('B', 'C')
        ORDER BY j.clientid, j.poolid, j.filesetid, j.realendtime DESC
    ) j ON j.clientid = c.clientid
    LEFT JOIN pool p ON p.poolid = j.poolid
    LEFT JOIN fileset f ON f.filesetid = j.filesetid;
""")  # (12)


def default_to_regular(d):
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in iteritems(d)}
    return d

    
def all_backups():
    """List all jobs by client and fileset."""
    con = None
    jobs = defaultdict(lambda: defaultdict(defaultdict))
    hosts = dict(host_up())
    try:
        con = psycopg2.connect(database='bareos', user='bareos', host='phserver01')
        con.set_session(readonly=True)
        cur = con.cursor()
        cur.execute("""
            SELECT c.name, p.name, j.jobbytes, j.realendtime, j.starttime, j.jobfiles, f.fileset,
            m.volumename, j.jobid
            FROM client c, job j, fileset f, pool p, media m, jobmedia jm
            WHERE j.jobstatus IN ('T', 'W') AND j.level IN ('F', 'I', 'D') AND j.type IN ('B', 'C')
            AND j.clientid=c.clientid AND j.poolid=p.poolid AND j.filesetid=f.filesetid AND
            jm.mediaid=m.mediaid AND jm.jobid=j.jobid;
        """)
        tuples = cur.fetchall()
        total_size = float()
        for t in tuples:
            client = t[0]
            pool = t[1]
            jobbytes = t[2]
            realendtime = t[3]
            starttime = t[4]
            jobfiles = t[5]
            fileset = t[6]
            volname = t[7]
            jobid = t[8]
            pool_sub_dict = defaultdict(list)
            pool_list = list()
            try:
                duration = realendtime - starttime
            except Exception as e:
                logger.debug(format_exception(e))
                continue
            seconds = duration.total_seconds()
            minutes = int((seconds % 3600) // 60)
            endtime = realendtime.strftime("%d.%m.%y %H:%M")
            jobgigabytes = int(jobbytes/1000000000)  # Round up roughly.
            current_time = datetime.datetime.now()
            pool_list = (volname, jobid, jobgigabytes, endtime, minutes, jobfiles)
            try:
                j = jobs[client][fileset][pool]
            except:
                jobs[client][fileset][pool] = set()
                j = jobs[client][fileset][pool]
            j.add(pool_list)
    except Exception as e:
        logger.debug(format_exception(e))
        pass
    jobs = default_to_regular(jobs)  # (5)
    for jck, jcv in iteritems(jobs):
        for jfk, jfv in iteritems(jcv):
            jobs[jck][jfk] = OrderedDict(sorted(iteritems(jobs[jck][jfk])))
            for jpk, jpv in iteritems(jfv):
                for jpe in jpv:
                    # outputs: (92, 85, '22.05.15 21:23', 16, 384467, 'Full-LT-0007')
                    total_size += jpe[2]
                jobs[jck][jfk][jpk] = sorted(jpv)
    jobs = OrderedDict(sorted(iteritems(jobs)))
    return {'jobs': jobs, 'hosts': hosts, 'total_size': total_size}


def recent():
    """Return recent dictionary with recent backups and hosts."""
    jobs_config, config_copy_dep = client_pool_map()
    config_copy_dep = dict(config_copy_dep)
    con = None
    try:
        con = psycopg2.connect(database='bareos', user='bareos', host='phserver01')
        con.set_session(readonly=True)
        cur = con.cursor()
        cur.execute(recent_qry)
        tuples = cur.fetchall()
        jobs = defaultdict(lambda: defaultdict(defaultdict))
        # jobs dict looks like: { client1 : { pool1 : [ jobbytes, realendtime, .. ], pool2 : [..] }, client2: {..}}
        clients_pools_dict = defaultdict(list)
        for t in tuples:
            client = t[0]
            fileset = t[6]
            pool = t[1]
            pool_sub_dict = defaultdict(list)
            pool_list = list()
            jobbytes = t[2]
            realendtime = t[3]
            starttime = t[4]
            try:
                duration = realendtime - starttime
            except:
                continue
            seconds = duration.total_seconds()
            minutes = int((seconds % 3600) // 60)
            endtime = realendtime.strftime("%d.%m.%y %H:%M")
            # grob aufrunden
            jobgigabytes = int(jobbytes / 1000000000)
            current_time = datetime.datetime.now()
            if isinstance(_timeouts, int):
                timeout_max = datetime.timedelta(days=_timeouts)
                if (current_time - realendtime) > timeout_max:
                    timeout = 1
                else:
                    timeout = 0
            elif isinstance(_timeouts, dict):
                for tk, tv in iteritems(_timeouts):
                    if pool in tv:  # checking if pool is in tv (list of pools from _timeouts)
                        timeout_max = datetime.timedelta(days=tk)
                        if (current_time - realendtime) > timeout_max:
                            timeout = 1
                        else:
                            timeout = 0
                        break
            pool_list = [jobgigabytes, endtime, minutes, t[5], timeout]
            jobs[client][fileset][pool] = pool_list
    except ValueError as err:
        logger.debug(err)
        logger.debug("Error in view.")
    # Here we sort our copy pool dependency dictionary before filling it into the client_pool dictionary.
    for key, li in iteritems(config_copy_dep):
        config_copy_dep[key] = sorted(li)
    # Here we add copy pools that are associated to a pool to the config client's pool dictionary (aka jobs_should).
    config_copy_dep = OrderedDict(sorted(iteritems(config_copy_dep)))
    # adding "copy dependend pools" to "jobs config pools"
    for cck, ccv in iteritems(jobs_config):  # config client key/val
        for cfk, cfv in iteritems(ccv):  # config fileset
            # config dep is just 1 level dict like so: {'Full-LT': ['Full-Copy-LT', 'Incremental-Copy-LT'], ...}
            for cdk, cdv in iteritems(config_copy_dep):
                if cdk in cfv:  # cfv is list of pools associated to fileset key
                    for cde in cdv:  # Copy dep element
                        jobs_config[cck][cfk].add(cde)  # adding dep pool to list client_fileset pools.
    for jck, jcv in iteritems(jobs_config):
        for cfk, cfv in iteritems(jcv):
            jobs_config[jck][cfk] = sorted(cfv)
    # Sorting in the end, so that set() doesnt get converted to list(), in order to have add() method available.
    jobs_config = OrderedDict(sorted(iteritems(jobs_config)))
    hosts = dict(host_up())
    # setting missing pools to value 0.
    # Comparing jobs_config with jobs dictionary in this view instead of in the template, that keeps the template
    # cleaner and in general easier to write.
    for jck, jcv in iteritems(jobs):
        for cck, ccv in iteritems(jobs_config):  # config_client_key/val
            # If job client key (is) == config client key (should)
            if jck == cck:
                for jfk, jfv in iteritems(jcv):
                    # cfv ^= list of all pools that *should* exist for each client's fileset.
                    for cfk, cfv in iteritems(ccv):
                        # if not checking for jfk==jfk, it'd get pools marked for filesets as missing though they're not
                        if jfk == cfk:
                            # jcv looks as such: ['Full-LT', 'Full-LT-Copies-01', 'Full-LT-Copies-02', 'Incremental-LT',
                            # 'Incremental-LT-Copies-01', 'Incremental-LT-Copies-02']
                            for cfe in cfv:
                                # jfv looks like: defaultdict(None, {'Full-ST': [181, '03.10.15 16:30', 30, 116172, 0],
                                # 'Incremental-ST': [2, '24.10.15 18:19', 0, 78, 0]})
                                if cfe not in jfv:
                                    # Set it to 0, not sure if it cascades with None
                                    jobs[jck][jfk][cfe] = 0
    # Converting back to dict so template can print it.
    jobs = default_to_regular(jobs)
    # Sorting
    for jck, jcv in iteritems(jobs):
        for jfk, jfv in iteritems(jcv):
            jobs[jck][jfk] = OrderedDict(sorted(iteritems(jobs[jck][jfk])))
    # A dict will always return keys/values in random order, that's why we have to use an "OrderedDict"
    jobs = OrderedDict(sorted(iteritems(jobs)))
    return {'jobs': jobs, 'hosts': hosts}
