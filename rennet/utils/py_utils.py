#  Copyright 2018 Fraunhofer IAIS. All rights reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""Pure Python utilities

@motjuste
Created: 10-10-2016
"""
from __future__ import print_function, division
import re
from sys import getsizeof
from numbers import Number
from collections import Set, Mapping, deque, namedtuple
from threading import Lock
from six.moves import range
from six import PY2

if not PY2:
    from math import gcd
else:
    from fractions import gcd


def is_string(obj):
    """ Returns true if s is string or string-like object,
    compatible with Python 2 and Python 3.
    """
    try:
        return isinstance(obj, basestring)
    except NameError:
        return isinstance(obj, str)


def cvsecs(time):
    """ Will convert any time into seconds.

    Here are the accepted formats:

    >>> cvsecs(15.4) -> 15.4 # seconds
    >>> cvsecs( (1,21.5) ) -> 81.5 # (min,sec)
    >>> cvsecs( (1,1,2) ) -> 3662 # (hr, min, sec)
    >>> cvsecs('01:01:33.5') -> 3693.5  #(hr,min,sec)
    >>> cvsecs('01:01:33.045') -> 3693.045
    >>> cvsecs('01:01:33,5') #coma works too

    """
    if is_string(time):
        if (',' not in time) and ('.' not in time):
            time = time + '.0'
        expr = r"(\d+):(\d+):(\d+)[,|.](\d+)"
        finds = re.findall(expr, time)[0]
        nums = [float(f) for f in finds]
        return (
            3600 * int(finds[0]) + 60 * int(finds[1]) + int(finds[2]) + nums[3] /
            (10**len(finds[3]))
        )

    elif isinstance(time, tuple):
        if len(time) == 3:
            hours, minutes, seconds = time
        elif len(time) == 2:
            hours, minutes, seconds = 0, time[0], time[1]
        return 3600 * hours + 60 * minutes + seconds

    else:
        return time


class BaseSlotsOnlyClass(object):  #pylint: disable=too-few-public-methods
    """ Slots only base class.

    Implements creating repr automatically.
    """
    # TODO: [ ] Dox
    # TODO: [ ] Tests!

    __slots__ = ()

    def __repr__(self):
        a_v = ((att, getattr(self, att)) for att in self.__slots__)
        r = ".".join((self.__module__.split(".")[-1], self.__class__.__name__))
        return r + "({})".format(", ".join("{!s}={!r}".format(*av) for av in a_v))


def getsize(obj_0):
    """Recursively iterate to sum size of object & members.

    Reference
        https://stackoverflow.com/a/30316760
    """
    try:  # Python 2
        zero_depth_bases = (basestring, Number, xrange, bytearray)
        iteritems = 'iteritems'
    except NameError:  # Python 3
        zero_depth_bases = (str, bytes, Number, range, bytearray)
        iteritems = 'items'

    _seen_ids = set()

    def inner(obj):
        obj_id = id(obj)
        if obj_id in _seen_ids:
            return 0
        _seen_ids.add(obj_id)
        size = getsizeof(obj)
        if isinstance(obj, zero_depth_bases):
            pass  # bypass remaining control flow and return
        elif isinstance(obj, (tuple, list, Set, deque)):
            size += sum(inner(i) for i in obj)
        elif isinstance(obj, Mapping) or hasattr(obj, iteritems):
            size += sum(inner(k) + inner(v) for k, v in getattr(obj, iteritems)())
        # Check for custom object instances - may subclass above too
        if hasattr(obj, '__dict__'):
            size += inner(vars(obj))
        if hasattr(obj, '__slots__'):  # can have __slots__ with __dict__
            size += sum(inner(getattr(obj, s)) for s in obj.__slots__ if hasattr(obj, s))
        return size

    return inner(obj_0)


def lowest_common_multiple(x, y):
    # gcd expects integers, the whole thing is integers, returning integers
    return abs(x * y) // gcd(x, y) if x and y else 0  # pylint: disable=deprecated-method


class ThreadSafeIterator(object):  # pylint: disable=too-few-public-methods
    def __init__(self, iterator):
        self.iterator = iterator
        self.lock = Lock()

    def __iter__(self):
        return self

    def next(self):
        with self.lock:
            return next(self.iterator)

    def __next__(self):
        return self.next()


def threadsafe_generator(f):
    def gen(*a, **k):
        return ThreadSafeIterator(f(*a, **k))

    return gen


def namedtuple_with_defaults(typename, field_names, default_values=()):
    """ namedtuple with default values
    Reference
    =========
    https://stackoverflow.com/a/18348004/2700777
    """
    T = namedtuple(typename, field_names)
    T.__new__.__defaults__ = (None, ) * len(T._fields)
    if isinstance(default_values, Mapping):
        prototype = T(**default_values)
    else:
        prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T


def recursive_glob(rootdir, pattern):
    """Search recursively for files matching a specified pattern.
    eff you py2

    Adapted from http://stackoverflow.com/questions/2186525
    """
    import fnmatch
    import os

    for root, _, filenames in os.walk(rootdir):
        for filename in fnmatch.filter(filenames, pattern):
            yield os.path.join(root, filename)


def makedirs_with_existok(name, exist_ok=False):
    import os

    if not PY2:
        os.makedirs(name, exist_ok=exist_ok)
    else:
        try:
            os.makedirs(name)
        except OSError:
            if exist_ok:
                pass
            else:
                raise
