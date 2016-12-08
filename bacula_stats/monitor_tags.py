from itertools import tee, islice, chain
from six import iteritems
import collections


def get_item(dictionary, key):
    return dictionary.get(key)


def gb_to_tb(gb):
    return gb/(1000)


def sort(dict):
    """ dict looks like: {'Full-ST': [(1,2,3), (2,3,4)], 'Incremental-ST': [(3,4,5), (4,5,6)] """
    tuple_list = list()
    for pk, pv in iteritems(dict):
        for t in pv:
            t = (pk,) + t
            tuple_list.append(t)
    return tuple_list


def client_fileset_size(dict):
    """ dict looks like: {'Full-ST': [(1,2,3), (2,3,4)], 'Incremental-ST': [(3,4,5), (4,5,6)] """
    tuple_list = list()
    gigabytes = float()
    for pk, pv in iteritems(dict):
        for t in pv:
            gigabytes += t[1]
    return "{0:.3f}".format(gigabytes/1024)


def previous_and_next(some_iterable):
    logger.error(datetime.datetime.now(), "latest_local")
    prevs, items, nexts = tee(some_iterable, 3)
    prevs = chain([None], prevs)
    nexts = chain(islice(nexts, 1, None), [None])
    return zip(prevs, items, nexts)


