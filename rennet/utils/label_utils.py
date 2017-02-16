"""
@motjuste
Created: 26-08-2016

Utilities for working with labels
"""
from __future__ import print_function, division
import numpy as np
from collections import Iterable
from contextlib import contextmanager


class SequenceLabels(object):
    """ Base class for working with contiguous labels for sequences

    By default the samplerate is 1, but a default one can be set at the time
    of instantiating. The samplerate should reflect the one used in calculating
    the starts_ends.

    The starts, ends and starts_ends can be retrieved at a different
    samplerate by using the `with SequenceLabel.samplerate_as(new_samplerate)`.
    While in the scope of the `with` context will act as if the samplerate is
    set to `new_samplerate`, except `SequenceLabel.samplerate`, which will
    always return the original samplerate.

    Supports normal slicing as in numpy, but the returned value will be another
    instance of the SequenceLabels class.

    This class is not a monolith, but should be able to work with normal
    numpy tricks. Plus, you should extend it for specific data, etc.

    Plus, there is nice printing.

    TODO: [A] Check if something can be done about plotting it nicely too!
    TODO: [ ] Export to ELAN
    """

    def __init__(self, starts_ends, labels, samplerate=1):
        assert all(isinstance(x, Iterable)
                   for x in [starts_ends, labels]), "starts_ends and labels" + \
                                                    " should be iterable"
        assert len(starts_ends) == len(labels), "starts_ends and labels" + \
                                                " mismatch in length "

        starts_ends = np.array(starts_ends)
        assert np.all(starts_ends[:, 1] - starts_ends[:, 0] >
                      0.), "(ends - starts) should be > 0 for all pairs"

        sidx = np.argsort(starts_ends[:, 0])  # save sorted by starts
        self._starts_ends = starts_ends[sidx]

        if isinstance(labels, np.ndarray):
            self.labels = labels[sidx]
        else:
            self.labels = [labels[i] for i in sidx]

        self._orig_samplerate = samplerate
        self._samplerate = samplerate

    @property
    def samplerate(self):
        # If you want to set a different samplerate, use samplerate_as
        # If you have made a mistake, create a new instance
        return self._samplerate  # always the current samplerate

    @property
    def orig_samplerate(self):
        # Changing the original samplerate may lead to wrong results
        # hence provided as a property to only read
        # No one's stopping them. Hoping the user is an adult
        return self._orig_samplerate

    @property
    def starts_ends(self):
        return self._starts_ends * (self.samplerate / self.orig_samplerate)

    @property
    def starts(self):
        return self.starts_ends[:, 0]

    @property
    def ends(self):
        return self.starts_ends[:, 1]

    @contextmanager
    def samplerate_as(self, new_sr):
        """ Temporarily change to a different samplerate to calculate values

        To be used with a `with` clause.

        The starts and ends will calculated on the contextually most up-to-date
        samplerate.
        """
        old_sr = self.samplerate
        self._samplerate = new_sr
        try:
            yield
        finally:
            self._samplerate = old_sr

    def _starts_ends_for_samplerate(self, samplerate):
        # Available to children classes and not expected to change in context
        if samplerate == self.samplerate:
            return self.starts_ends
        else:
            # Change the context to the new samplerate
            # even if the self.samplerate was set to a different contextual one
            # the starts_ends will be calculated for given samplerate
            # and the contextual samplerate will be returned
            with self.samplerate_as(samplerate):
                return self.starts_ends

    def _labels_at_ends_naivepy(self, se, ends, default_label):
        """ Implementation of the algorithm to find labels for ends """
        l = []
        for end in ends:
            end_label = []
            for i, (s, e) in enumerate(se):
                if s < end <= e:
                    end_label.append(self.labels[i])

            if len(end_label) == 0:
                end_label = default_label

            l.append(end_label)

        return l

    def _labels_at_ends_numpy_forlends_forlabel(self, se, ends, default_label):
        idx = (se[:, 0][np.newaxis, :] < ends[:, np.newaxis]) & (
            se[:, 1][np.newaxis, :] >= ends[:, np.newaxis])

        l = []
        for i in range(len(ends)):
            l_idx = np.where(idx[i, :])[0]
            if len(l_idx) == 0:
                l.append(default_label)
            else:
                l.append([self.labels[li] for li in l_idx])

        return l

    def labels_at(self, ends, samplerate=None, default_label=None):
        if not isinstance(ends, Iterable):
            ends = [ends]

        ends = np.array(ends)

        # make sure we are working with the correct samplerate for starts_ends
        if samplerate is None:
            # Assume the user is expecting the current samplerate
            # self.samplerate always has the most up to date samplerate
            se = self.starts_ends
        else:
            se = self._starts_ends_for_samplerate(samplerate)

        se = np.round(se, 10)  # To avoid issues with floating points
        # Yes, it looks arbitrary
        # There will be problems later in comparing floating point numbers
        # esp when testing for equality to the ends
        # the root of the cause is when the provided samplerate is higher than
        # the orig_samplerate, esp when the ratio is irrational.
        # A max disparity of 16000:1 gave correct results
        # limited to the tests of course. Please look at the corresponding tests
        #
        # FIXME: It should not be the case anyway. All the trouble to support
        #       arbitrary self.orig_samplerate and samplerate
        #

        # return self._labels_at_ends_naivepy(se, ends, default_label)   # slower
        return self._labels_at_ends_numpy_forlends_forlabel(se, ends,
                                                            default_label)

    def __len__(self):
        return len(self.starts_ends)

    def __getitem__(self, idx):
        se = self._starts_ends[idx]
        l = self.labels[idx]

        if isinstance(idx, int):  # case with only one segment
            se = np.expand_dims(se, axis=0)  # shape (2,) to shape (1, 2)
            l = [l]

        sr = self.samplerate

        return SequenceLabels(se, l, sr)

    def __str__(self):
        s = self.__class__.__name__ + " with sample rate: " + str(
            self.samplerate)
        s += "\n"
        s += "{:8} - {:8} : {}\n".format("Start", "End", "Label")
        s += "\n".join("{:<8.4f} - {:<8.4f} : {}".format(s, e, str(l))
                       for (s, e), l in zip(self.starts_ends, self.labels))

        return s


class ContiguousSequenceLabels(SequenceLabels):
    """ Special SequenceLabels with contiguous labels

    There is a label for each sample between min(starts) and max(ends)

    """

    def __init__(self, *args, **kwargs):
        super(ContiguousSequenceLabels, self).__init__(*args, **kwargs)
        # the starts_ends were sorted in __init__ on starts
        assert np.all(np.diff(self.starts) >
                      0.), "There are multiple segments with the same starts"
        assert np.all(
            self.starts_ends[1:, 0] == self.starts_ends[:-1, 1]
        ), "All ends should be the starts of the next segment, except the last"

        # IDEA: store only the unique values? min_start and ends?
        # May be pointless here in python

    def _labels_at_ends_naivepy(self, se, ends, default_label):
        l = []
        for end in ends:
            for i, (s, e) in enumerate(se):
                if s < end <= e:
                    l.append(self.labels[i])
                    break  # there is only one segment where end can be
            else:  # if the for loop didn't break
                l.append(default_label)

        return l

    def _labels_at_ends_numpy_forlends_forlabel(self, se, ends, default_label):
        raise NotImplementedError()

    def labels_at(self, ends, samplerate=None, default_label=None):
        if not isinstance(ends, Iterable):
            ends = [ends]

        ends = np.array(ends)

        # make sure we are working with the correct samplerate for starts_ends
        if samplerate is None:
            # Assume the user is expecting the current samplerate
            # self.samplerate always has the most up to date samplerate
            se = self.starts_ends
        else:
            se = self._starts_ends_for_samplerate(samplerate)

        se = np.round(se, 10)  # To avoid issues with floating points
        # Yes, it looks arbitrary. Check SequenceLabels.labels_at(...)
        #
        # FIXME: It should not be the case anyway. All the trouble to support
        #       arbitrary self.orig_samplerate and samplerate
        #

        # all ends are within the segments
        endings = se[:, 1]
        maxend = endings.max()
        minstart = endings.min()
        endswithin = (ends > minstart) & (ends <= maxend)

        if len(endswithin) == len(ends):
            # all ends are within
            # raise NotImplementedError()
            return self._labels_at_ends_naivepy(se, ends, default_label)
        # else:
        #     endsleft = (ends <= minstart)
        #     endsright = (ends > maxend)

        # we need to behave appropriately for default_label

        # NOTE: if default_label provided is of the same type and shape
        # as of elements of self.labels, then, the returned labels will be
        # of the same type of self.labels
        # ELSE, it will be a list with elements of type self.labels
        # where ends are within, and default_label otherwise
        if (isinstance(self.labels, np.ndarray) and
                isinstance(default_label, type(self.labels[0]))):
            if (isinstance(default_label, np.ndarray) and
                    default_label.shape != self.labels[0].shape):
                # np.concatenate will not work raise error
                msg = """ default_label is not the same shape as any element of labels """
                raise ValueError(msg)

            # np.concatenate should work
            # and so should using np.empty_like(self.labels, ...)
            # or, they gonna raise errors
            # raise NotImplementedError()
            return self._labels_at_ends_naivepy(se, ends, default_label)
        else:
            # return list with self.labels for ends_within, default_label otherwise
            # raise NotImplementedError()
            return self._labels_at_ends_naivepy(se, ends, default_label)
