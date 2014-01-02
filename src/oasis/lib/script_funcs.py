# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" A collection of functions that may be called by
    scripts. eg. the __marker.py and __results.py scripts.
"""

from Audit import audit
from oasis.models.Question import Question
from oasis.models.QTemplate import QTemplate

# We dont want the scripts playing with their questionID (qid) so we have to
# wrap all the functions that need it as an argument.


def withinTolerance(guess, correct, tolerance):
    """ Is the guess within tolerance % of the correct answer?
    """

    try:
        lower = correct - (abs(correct) * (tolerance / 100))
        upper = correct + (abs(correct) * (tolerance / 100))
    except (TypeError, ValueError):
        lower = None
        upper = None

    if upper < lower:
        tmp = lower
        lower = upper
        upper = tmp

    try:
        guess = float(guess)
    except (ValueError, TypeError):
        guess = None

    # noinspection PyComparisonWithNone
    if guess == None:  # guess could be 0
        return False

    if lower <= guess <= upper:
        return True

    return False


def marker_log_fn(qid):
    """ When a marker script wishes to log an error, it comes through here.
    """
    def real_markerlog(priority, mesg):
        """__marker.py has log() 'ed an error"""
        q_log(qid, priority, '__marker.py', mesg)

    return real_markerlog


def result_log_fn(qid):
    """ When a result script wishes to log an error, it comes through here.
    """
    def real_resultlog(priority, mesg):
        """__result.py has log() 'ed an error"""
        q_log(qid, priority, '__result.py', mesg)

    return real_resultlog


def q_log(qid, priority, facility, mesg):
    """function for question scripts (marker, render, generator, etc) to
       use to log messages. """
    qid = int(qid)
    q = Question.get(qid)
    qt = QTemplate.get(q.qtemplate)
    audit(3, qt.owner, qt.id, "qlogger", "version=%s,variation=%s,priority=%s,facility=%s,message=%s" % (q.version, q.variation, priority, facility, mesg))

