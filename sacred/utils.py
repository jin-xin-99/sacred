#!/usr/bin/env python
# coding=utf-8

from __future__ import division, print_function, unicode_literals
import collections
from contextlib import contextmanager
import logging
import random
import sys


__sacred__ = True  # marker for filtering stacktraces when run from commandline


if sys.version_info[0] == 3:
    import io
    StringIO = io.StringIO
else:
    from StringIO import StringIO

NO_LOGGER = logging.getLogger('ignore')
NO_LOGGER.disabled = 1
SEEDRANGE = (1, 1e9)


def create_basic_stream_logger(name, level=None):
    level = level if level is not None else logging.INFO
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers = []
    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


def recursive_update(d, u):
    """
    Given two dictionaries d and u, update dict d recursively.

    E.g.:
    d = {'a': {'b' : 1}}
    u = {'c': 2, 'a': {'d': 3}}
    => {'a': {'b': 1, 'd': 3}, 'c': 2}
    """
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = recursive_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


class Tee(object):
    def __init__(self, out1, out2):
        self.out1 = out1
        self.out2 = out2

    def write(self, data):
        self.out1.write(data)
        self.out2.write(data)

    def flush(self):
        self.out1.flush()
        self.out2.flush()


@contextmanager
def tee_output():
    out = StringIO()
    sys.stdout = Tee(sys.stdout, out)
    sys.stderr = Tee(sys.stderr, out)
    yield out
    sys.stdout = sys.stdout.out1
    sys.stderr = sys.stderr.out1
    out.close()


def get_seed(rnd=None):
    if rnd is None:
        return random.randint(*SEEDRANGE)
    return rnd.randint(*SEEDRANGE)


def create_rnd(seed):
    return random.Random(seed)


def iterate_separately(dictionary):
    """
    Iterate over the items of a dictionary. First iterate over all items that
    are non-dictionary values (sorted by keys), then over the rest
    (sorted by keys).
    """
    single_line_keys = [k for k in dictionary.keys()
                        if not isinstance(dictionary[k], dict)]
    for k in sorted(single_line_keys):
        yield k, dictionary[k]

    multi_line_keys = [k for k in dictionary.keys()
                       if isinstance(dictionary[k], dict)]
    for k in sorted(multi_line_keys):
        yield k, dictionary[k]


def iterate_flattened(d):
    """
    Iterate over a dictionary recursively, providing full dotted
    paths for every leaf.
    """
    for key in sorted(d.keys()):
        value = d[key]
        if isinstance(value, dict):
            for k, v in iterate_flattened(d[key]):
                yield join_paths(key,  k), v
        else:
            yield key, value


def set_by_dotted_path(d, path, value):
    """
    Set an entry in a nested dict using a dotted path. Will create dictionaries
    as needed.

    Examples:
    >>> d = {'foo': {'bar': 7}}
    >>> set_by_dotted_path(d, 'foo.bar', 10)
    >>> d
    {'foo': {'bar': 10}}
    >>> set_by_dotted_path(d, 'foo.d.baz', 3)
    >>> d
    {'foo': {'bar': 10, 'd': {'baz': 3}}}
    """
    split_path = path.split('.')
    current_option = d
    for p in split_path[:-1]:
        if p not in current_option:
            current_option[p] = dict()
        current_option = current_option[p]
    assert split_path[-1], "empty path or trailing dot ('%s')" % path
    current_option[split_path[-1]] = value


def get_by_dotted_path(d, path):
    """
    Get an entry from nested dictionaries using a dotted path.

    Example:
    >>> get_by_dotted_path({'foo': {'a': 12}}, 'foo.a')
    12
    """
    if not path:
        return d
    split_path = path.split('.')
    current_option = d
    for p in split_path:
        if p not in current_option:
            return None
        current_option = current_option[p]
    return current_option


def iter_path_splits(path):
    """
    Iterate over possible splits of a dotted path. The first part can be empty
    the second should not be.

    Example:
    >>> list(iter_path_splits('foo.bar.baz'))
    [('',        'foo.bar.baz'),
     ('foo',     'bar.baz'),
     ('foo.bar', 'baz')]
    """
    split_path = path.split('.')
    for i in range(len(split_path)):
        p1 = join_paths(*split_path[:i])
        p2 = join_paths(*split_path[i:])
        yield p1, p2


def iter_prefixes(path):
    """
    Iterate through all (non-empty) prefixes of a dotted path.

    Example:
    >>> list(iter_prefixes('foo.bar.baz'))
    ['foo', 'foo.bar', 'foo.bar.baz']
    """
    split_path = path.split('.')
    for i in range(1, len(split_path) + 1):
        yield join_paths(*split_path[:i])


def join_paths(*parts):
    """
    Join different parts together to a valid dotted path.
    """
    return '.'.join(p.strip('.') for p in parts if p)


def is_prefix(pre_path, path):
    """
    Returns True if pre_path is a path-prefix of path.
    """
    pre_path = pre_path.strip('.')
    path = path.strip('.')
    return not pre_path or path.startswith(pre_path + '.')


def convert_to_nested_dict(dotted_dict):
    """
    Convert a dictionary where some of the keys might be dotted paths to the
    corresponding nested dictionary.
    """
    nested_dict = {}
    for k, v in iterate_flattened(dotted_dict):
        set_by_dotted_path(nested_dict, k, v)
    return nested_dict
