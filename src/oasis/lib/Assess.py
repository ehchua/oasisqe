# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Assessment related functionality.
"""

import re

from oasis.lib.OaExceptions import OaMarkerError
from logging import log, INFO, ERROR, WARN
from oasis.lib import DB, General
from oasis.models.Course import Course
from oasis.models.Exam import Exam
from oasis.models.Question import Question
from oasis.models.QTemplate import QTemplate

DATEFORMAT = "%d %b %H:%M"


def mark_exam(user_id, exam_id):
    """ Submit the assessment and mark it.
        Returns True if it went well, or False if a problem.
    """
    exam = Exam.get(exam_id)
    uexam = exam.by_student(user_id)
    numQuestions = exam.get_num_questions()
    status = exam.get_user_status(user_id)
    log(INFO,
        "Marking assessment %s for %s, status is %s" %
        (exam_id, user_id, status))
    examtotal = 0.0
    for position in range(1, numQuestions + 1):
        q_id = General.get_exam_q(exam_id, position, user_id)
        answers = Question.get_q_guesses(q_id)
        # There's a small chance they got here without ever seeing a question,
        # make sure it exists.
        DB.add_exam_q(user_id, exam_id, q_id, position)

        # First, mark the question
        try:
            marks = General.mark_q(q_id, answers)
            DB.set_q_status(q_id, 3)    # 3 = marked
            DB.set_q_marktime(q_id)
        except OaMarkerError:
            log(WARN,
                "Marker Error in question %s, exam %s, student %s!" %
                (q_id, exam_id, user_id))
            return False
        parts = [int(var[1:])
                 for var in marks.keys()
                 if re.search("^A([0-9]+)$", var) > 0]
        parts.sort()

        # Then calculate the mark
        total = 0.0
        for part in parts:
            try:
                mark = float(marks['M%d' % (part,)])
            except (KeyError, ValueError):
                mark = 0
            total += mark
            DB.update_q_score(q_id, total)
        examtotal += total

    exam.set_user_status(user_id, exam_id, 5)
    exam.set_submit_time(user_id, exam_id)
    exam.save_score(exam_id, user_id, examtotal)
    exam.touchUserExam(exam_id, user_id)

    log(INFO,
        "user %s scored %s total on exam %s" %
        (user_id, examtotal, exam_id))
    return True


def student_exam_duration(student, exam_id):
    """ How long did the assessment take.
        returns   starttime, endtime
        either could be None if it hasn't been started/finished
    """

    firstview = None

    exam = Exam.get(exam_id)
    examsubmit = exam.get_submit_time(student)
    questions = General.get_exam_qs(student, exam_id)

    # we're working out the first time the assessment was viewed is the
    # earliest time a question in it was viewed
    # It's possible (although unlikely) that they viewed a question
    # other than the first page, first.
    for question in questions:
        questionview = DB.get_q_viewtime(question)
        if firstview:
            if questionview < firstview:
                firstview = questionview
        else:
            firstview = questionview
    return firstview, examsubmit


def render_own_marked_exam(student, exam):
    """ Return a students instance of the exam, with HTML
        version of the question,
        their answers, and a marking summary.

        returns list of questions/marks
        [  {'pos': position,
            'html': rendered (marked) question,
            'marking': [ 'part': part number,
                         'guess':   student guess,
                         'correct': correct answer,
                         'mark':    (float) mark,
                         'tolerance':  marking tolerance,
                         'comment':   marking comment
                         ]
           }, ...
        ]
    """
    questions = General.get_exam_qs(student, exam)
    firstview, examsubmit = student_exam_duration(student, exam)
    results = []

    if not examsubmit:
        return [{'pos':1,
                'html': "In Progress",
                'marking': {}
        },], False
    examtotal = 0.0
    for q_id in questions:
        q = Question.get(q_id)
        qt = QTemplate.get(q.qtemplate)

        answers = DB.get_q_guesses_before_time(q_id, examsubmit)
        pos = DB.get_qt_exam_pos(exam, qt.id)
        marks = General.mark_q(q_id, answers)
        parts = [int(var[1:])
                 for var in marks.keys()
                 if re.search("^A([0-9]+$)", var) > 0]
        parts.sort()
        marking = []
        for part in parts:
            guess = marks['G%d' % (part,)]

            if guess == "None":
                guess = None
            answer = marks['A%d' % (part,)]
            score = marks['M%d' % (part,)]
            tolerance = marks['T%d' % (part,)]
            comment = marks['C%d' % (part,)]
            examtotal += score
            marking.append({
                'part': part,
                'guess': guess,
                'correct': answer,
                'mark': score,
                'tolerance': tolerance,
                'comment': comment
            })

        html = General.render_q_html(q_id)
        results.append({
            'pos': pos,
            'html': html,
            'marking': marking
        })
    return results, examtotal


def get_exam_list_sorted(user_id, prev_years=False):
    """ Return a list of exams for the given user. """
    courses = Course.all()
    exams = []
    for course in courses:
        try:
            exams += Exam.by_course(course, prev_years=prev_years)
        except KeyError, err:
            log(ERROR,
                "Failed fetching exam list for user %s: %s" %
                (user_id, err))
    exams.sort(key=lambda y: y.start, reverse=True)
    return exams
