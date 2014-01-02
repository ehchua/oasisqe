# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Views related to the practice section
"""

import os

from flask import render_template, session, request, abort
from logging import log, ERROR
from oasis.lib import DB, Practice, General, Setup
MYPATH = os.path.dirname(__file__)
from oasis.models.Permission import Permission
from oasis.models.Topic import Topic
from oasis.models.Course import Course
from oasis.models.Question import Question
from oasis.models.QTemplate import QTemplate

from oasis import app
from .lib.Util import authenticated


@app.route("/practice/top")
@authenticated
def practice_top():
    """ Present the top level practice page - let them choose a course """
    return render_template(
        "practicetop.html",
        courses=Course.all()
    )


@app.route("/practice/coursequestions/<int:course_id>")
@authenticated
def practice_choose_topic(course_id):
    """ Present a list of topics for them to choose from the given course """
    user_id = session['user_id']
    try:
        course = Course.get(course_id)
    except KeyError:
        course = None
        abort(404)
    try:
        topics = course.topics()
    except KeyError:
        topics = []
        abort(404)

    members = []
    for topic in topics:
        if topic.visibility == 2:  # course only
            if not members:
                members = course.get_users()
            if not user_id in members:
                topics.remove(topic)
    return render_template(
        "practicecourse.html",
        courses=Course.all(),
        canpreview=Permission.check_perm(user_id, course_id, "questionpreview"),
        topics=topics,
        course=course
    )


@app.route("/practice/subcategory/<int:topic_id>")
@authenticated
def practice_choose_question(topic_id):
    """ Present a list of questions for them to choose from the given topic """
    user_id = session['user_id']
    topic = Topic.get(topic_id)
    course = Course.get(topic.course)
    topics = []
    try:
        topics = course.topics()
    except KeyError:
        abort(404)
    questions = Practice.get_sorted_questions(course.id, topic_id, user_id)

    members = []
    if topic.visibility == 2:  # course only
        if not members:
            members = course.get_users()
            if not user_id in members:
                abort(404)

    for topic in topics:
        if topic.visibility == 2:  # course only
            if not members:
                members = course.get_users()
            if not user_id in members:
                topics.remove(topic)

    return render_template(
        "practicetopic.html",
        canpreview=Permission.check_perm(user_id, course.id, "questionpreview"),
        topics=topics,
        topic_id=topic_id,
        course=course,
        topictitle=topic.title,
        questions=questions
    )


@app.route("/practice/statsfortopic/<int:topic_id>")
@authenticated
def practice_choose_question_stats(topic_id):
    """ Present a list of questions for them to choose from the given topic,
        and show some statistics on how they're doing.
    """
    user_id = session['user_id']
    topic = Topic.get(topic_id)
    course = topic.course

    topics = course.topics()
    questions = Practice.get_sorted_qlist_wstats(course.id, topic_id, user_id)

    return render_template(
        "practicetopicstats.html",
        canpreview=Permission.check_perm(user_id, course.id, "questionpreview"),
        topics=topics,
        topic_id=topic_id,
        course=course,
        topictitle=topic.title,
        questions=questions
    )


@app.route("/practice/question/<int:topic_id>/<int:qt_id>",
           methods=['POST', 'GET'])
@authenticated
def practice_do_question(topic_id, qt_id):
    """ Show them a question and allow them to fill in some answers """
    user_id = session['user_id']
    topic = Topic.get(topic_id)
    course = Course.get(topic.course)

    try:
        qtemplate = DB.get_qtemplate(qt_id)
    except KeyError:
        qtemplate = None
        abort(404)
    questions = Practice.get_sorted_questions(course.id, topic_id, user_id)
    q_title = qtemplate['title']
    q_pos = DB.get_qtemplate_topic_pos(qt_id, topic_id)

    blocked = Practice.is_q_blocked(user_id, course.id, topic_id, qt_id)
    if blocked:
        return render_template(
            "practicequestionblocked.html",
            mesg=blocked,
            topictitle=topic.title,
            topic_id=topic_id,
            qt_id=qt_id,
            course=course,
            q_title=q_title,
            questions=questions,
            q_pos=q_pos,
        )

    try:
        q_id = Practice.get_practice_q(qt_id, user_id)
    except (ValueError, TypeError), err:
        log(ERROR,
            "ERROR 1001  (%s,%s) %s" % (qt_id, user_id, err))
        return render_template(
            "practicequestionerror.html",
            mesg="Error generating question.",
            topictitle=topic.title,
            topic_id=topic_id,
            qt_id=qt_id,
            course=course,
            q_title=q_title,
            questions=questions,
            q_pos="?",
        )

    if not q_id > 0:
        return render_template(
            "practicequestionerror.html",
            mesg="Error generating question.",
            topictitle=topic.title,
            topic_id=topic_id,
            qt_id=qt_id,
            course=course,
            q_title=q_title,
            questions=questions,
            q_pos="?",
        )

    q_body = General.render_q_html(q_id)
    q_body = q_body.replace(r"\240", u" ")  # TODO: why is this here?

    return render_template(
        "practicedoquestion.html",
        q_body=q_body,
        topictitle=topic.title,
        topic_id=topic_id,
        qt_id=qt_id,
        course=course,
        q_title=q_title,
        questions=questions,
        q_pos=q_pos,
        q_id=q_id,
    )


@app.route("/practice/markquestion/<int:topic_id>/<int:question_id>",
           methods=['POST', ])
@authenticated
def practice_mark_question(topic_id, question_id):
    """ Mark the submitted question answersjust wa """
    user_id = session['user_id']
    topic = Topic.get(topic_id)
    course = Course(topic.course)
    q = Question.get(question_id)

    qt = QTemplate.get(q.qtemplate)
    questions = Practice.get_sorted_questions(course.id, topic_id, user_id)
    q_pos = DB.get_qtemplate_topic_pos(qt.id, topic_id)

    blocked = Practice.is_q_blocked(user_id, course.id, topic_id, qt.id)
    if blocked:
        return render_template(
            "practicequestionblocked.html",
            mesg=blocked,
            topictitle=topic.title,
            topic_id=topic_id,
            qt_id=qt.id,
            course=course,
            q_title=q.title,
            questions=questions,
            q_pos=q_pos,
        )

    marking = Practice.mark_q(user_id, topic_id, question_id, request)
    prev_id, next_id = Practice.get_next_prev(qt.id, topic_id)

    return render_template(
        "practicemarkquestion.html",
        topictitle=topic.title,
        topic_id=topic.id,
        qt_id=qt.id,
        course=course,
        q_title=q.title,
        questions=questions,
        q_pos=q_pos,
        q_id=question_id,
        marking=marking,
        next_id=next_id,
        prev_id=prev_id
    )
