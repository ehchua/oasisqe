# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Exam.py
    Handle exam related operations.
"""

import time
import json
import datetime
from logging import log, INFO, ERROR

from oasis.lib.OaTypes import todatetime
from oasis.lib import Util

from oasis import db

from oasis.models.Course import Course
from oasis.models.Permission import Permission

from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime


class Exam(db.Model):

    __tablename__ = "exams"

# CREATE TABLE exams (
#    "exam" SERIAL PRIMARY KEY,
#    "title" character varying(128) NOT NULL,
#    "owner" integer,
#    "type" integer,
#    "start" timestamp without time zone,
#    "end" timestamp without time zone,
#    "description" text,
#    "comments" text,
#    "course" integer,
#    "archived" integer DEFAULT 0,
#    "duration" integer,
#    "markstatus" integer DEFAULT 1,
#    "code" character varying,
#    "instant" integer
#);

    id = Column("exam", Integer, primary_key=True)
    title = Column("title", String(128), unique=True)
    instructions = Column("description", Text)
    owner = Column(Integer, ForeignKey('users.id'))
    type = Column(Integer)
    start = Column(DateTime)
    end = Column(DateTime)
    comments = Column(Text)
    course = Column(Integer, ForeignKey('courses.course'))
    archived = Column(Integer, default=0)
    duration = Column(Integer)
    markstatus = Column(Integer, default=1)
    code = Column(String(120))
    instant = Column(Integer)

    @staticmethod
    def create(course, owner, title, examtype, duration, start, end,
               instructions, code=None, instant=1):
        """ Add an assessment to the database."""

        newe = Exam()
        newe.course = course.id
        newe.owner = owner
        newe.title = title
        newe.type = examtype
        newe.duration = duration
        newe.start = start
        newe.end = end
        newe.instructions = instructions
        newe.code = code
        newe.instant = instant

        log(INFO, "Create Exam on course %s '%s'" % (course.id, title))

        return newe

    def save_score(self, student, examtotal):
        """ Store the exam score.
            Currently puts it into the marklog.
        """
        now = datetime.datetime.now()
        db.insert("marklog", values={'eventtime': now,
                                     'exam': self.id,
                                     'student': student,
                                     'marker': 1,
                                     'operation': "Submitted",
                                     'value': examtotal
        })
        self.touch_user_exam(student)

    @staticmethod
    def by_course(course, prev_years=False):
        """ Return a summary of information about all current exams in the course
            {id, course, name, description, start, duration, end, type}
        """
        if prev_years:
            return Exam.query.filter_by(course=course.id, archived=0).order_by("start")

        now = datetime.datetime.today()
        thisyear = datetime.datetime(now.year, 1, 1)

        return Exam.query.filter(Exam.end >= thisyear).filter_by(course=course.id, archived=0).order_by("start")

    def get_student_start_time(self, student):
        """ Return the time the student started an assessment as
            a datetime object or None
        """
        ret = run_sql("""SELECT firstview FROM questions
                        WHERE exam=%s AND student=%s ORDER BY firstview ASC LIMIT 1;""", (exam, student))
        if ret:
            firstview = ret[0][0]
            if firstview:
                return todatetime(firstview)
        return None

    def get_mark_time(self, student):
        """ Return the time the student submitted an assessment
            Returns a datetime object or None
        """
        assert isinstance(exam, int)
        assert isinstance(student, int)
        ret = run_sql("""SELECT marktime
                         FROM questions
                         WHERE exam=%s
                           AND student=%s
                         ORDER BY marktime DESC
                         LIMIT 1;""", (exam, student))
        if ret:
            lastview = ret[0][0]
            if lastview:
                return todatetime(lastview)
        return None

    def get_submit_time(self, student):
        """ Return the time the exam was submitted for marking.
            Returns a datetime object or None
        """
        submittime = None
        res = run_sql("SELECT submittime FROM userexams WHERE exam = %s AND student = %s;",
                      (exam_id, student))
        if res:
            submittime = res[0][0]
        if submittime is None:
            return None
        return todatetime(submittime)

    def is_done_by(self, user):
        """ Return True if the user has submitted the exam. We currently look for an entry in marklog."""
        ret = run_sql("SELECT marker FROM marklog WHERE exam=%s AND student=%s;",
                      (exam, user))
        # FIXME:  This can now be handled by the userexams status, but since
        # we have a lot of old data that hasn't been updated we need to stay
        # doing this the old way for now.
        if ret:
            return True
        return False

    def get_user_status(self, student):
        """ Returns the status of the particular exam instance.
            -1 = instance not found
            0 = not generated
            1 = unseen
            2 = started
            3 = out of time
            4 = submitted, not marked
            5 = marked, preliminary
            6 = marked, official
            7 = broken (will be hidden)
        """
        res = run_sql("""SELECT status FROM userexams WHERE exam=%s AND student=%s;""", (exam, student))
        if res:
            return int(res[0][0])
        log(ERROR, "Unable to get user %s status for exam %s! " % (student, exam))
        return -1

    def set_user_status(self, student, status):
        """ Set the status of a particular exam instance. """
        prevstatus = get_user_status(student, exam)
        if prevstatus <= 0:
            create_user_exam(student, exam)
        run_sql("""UPDATE userexams SET status=%s WHERE exam=%s AND student=%s;""", (status, exam, student))
        newstatus = get_user_status(student, exam)
        if not newstatus == status:
            log(ERROR, "Failed to set new status:  setUserStatus(%s, %s, %s)" % (student, exam, status))
        touchUserExam(exam, student)

    def create_user_exam(self, student):
        """ Create a new instance of an exam for a student."""
        status = get_user_status(student, exam)
        if status == -1:
            run_sql("""INSERT INTO userexams (exam, student, status, score)
                        VALUES (%s, %s, '1', '-1'); """, (exam, student))

    def get_end_time(self, user):
        """ Return the time that an exam ends for the given user. """
        ret = run_sql("""SELECT endtime FROM examtimers WHERE exam=%s AND userid=%s;""", (exam, user))
        if ret:
            return float(ret[0][0])
        ret = run_sql("SELECT duration FROM exams where exam=%s;", (exam,))
        duration = int(ret[0][0])
        nowtime = time.time()
        endtime = nowtime + (duration * 60)
        run_sql("""INSERT INTO examtimers (userid, exam, endtime)
                   VALUES (%s, %s, %s)""", (user, exam, endtime))
        return float(endtime)

    def get_num_questions(self):
        """ Return the number of questions in the exam."""
        ret = run_sql("""SELECT position FROM examqtemplates WHERE exam=%s GROUP BY position;""", (exam_id,))
        if ret:
            return len(ret)
        log(ERROR, "Request for unknown exam %s" % exam_id)
        return 0

    @staticmethod
    def get_exams_done(user):
        """ Return a list of assessments done by the user."""
        ret = run_sql("SELECT exam FROM examquestions WHERE student = %s GROUP BY exam", (user,))
        if not ret:
            return []
        exams = [int(row[0]) for row in ret]
        return exams

    def set_submit_time(self, student, submittime=None):
        """Set the submit time of the exam instance to a given time, or NOW() """
        if submittime:
            run_sql("""UPDATE userexams SET submittime=%s WHERE exam=%s AND student=%s;""", (submittime, exam, student))
        else:
            run_sql("""UPDATE userexams SET submittime=NOW() WHERE exam=%s AND student=%s;""", (exam, student))
        touchUserExam(exam, student)

    def resetEndTime(self, user):
        """ Reset the Exam timer for the student. This should let them resit the exam. """
        run_sql("DELETE FROM examtimers WHERE exam=%s AND userid=%s;", (exam, user))
        log(INFO, "Exam %s timer reset for user %s" % (exam, user))
        touchUserExam(exam, user)

    def reset_submit_time(self, user):
        """ Reset the Exam submit time for the student. This should let them resit
            the exam.
        """
        sql = "UPDATE userexams SET submittime = NULL WHERE exam=%s AND student=%s;"
        params = (exam, user)
        run_sql(sql, params)
        log(INFO, "Exam %s submit time reset for user %s" % (exam, user))
        touchUserExam(exam, user)

    def touchUserExam(self, user):
        """ Update the lastchange field on a user exam so other places can tell that
            something changed. This should probably be done any time one of the
            following changes:
                userexam fields on that row
                question/guess in the exam changes
        """
        DB.touch_user_exam(exam, user)

    def reset_mark(self, user):
        """ Remove the final mark for the student.
            This should let them resit the exam.
        """
        assert isinstance(exam, int)
        assert isinstance(user, int)
        run_sql("DELETE FROM marklog WHERE exam=%s AND student=%s;", (exam, user))
        log(INFO, "Exam %s mark reset for user %s" % (exam, user))
        touchUserExam(exam, user)

    def get_qts(self):
        """Return an ordered list of qtemplates used in the exam. """
        assert isinstance(exam, int)
        ret = run_sql("""SELECT position, qtemplate FROM examqtemplates WHERE exam=%s ORDER BY position;""", (exam,))
        if ret:
            return [int(row[1]) for row in ret]
        log(ERROR, "Request for unknown exam %s or exam has no qtemplates." % exam)
        return []

    def get_qts_list(self):
        """Return a list of qtemplates used in the exam."""
        assert isinstance(exam, int)
        ret = run_sql("""SELECT examqtemplates.qtemplate, examqtemplates.position,
                                qtemplates.title, questiontopics.topic,
                                questiontopics.position
                         FROM examqtemplates, qtemplates, questiontopics
                         WHERE examqtemplates.qtemplate=qtemplates.qtemplate
                           AND questiontopics.qtemplate=examqtemplates.qtemplate
                           AND examqtemplates.exam=%s
                         ORDER BY examqtemplates.position;""", (exam,))
        positions = {}
        if ret:
            position = None
            for row in ret:
                if not position == int(row[1]):
                    position = int(row[1])
                    positions[position] = []
                positions[position].append({'id': int(row[0]),
                                            'name': row[2],
                                            'position': int(row[1]),
                                            'topic': int(row[3]),
                                            'topicposition': int(row[4])})
        return [positions[p] for p in positions.keys()]

    def get_num_done(self, group=None):
        """Return the number of exams completed by the given group"""
        assert isinstance(exam, int)
        assert isinstance(group, int) or group is None
        if group:
            sql = """SELECT count(userexams.status)
                    FROM userexams,usergroups
                    WHERE userexams.student = usergroups.userid
                    AND usergroups.groupid = %s
                    AND exam = %s
                    AND status >= 4
                    AND status <=6;"""
            params = (group, exam)
        else:
            sql = "SELECT count(status) FROM userexams WHERE exam = %s AND status >= 4 AND status <=6;"
            params = (exam, )

        ret = run_sql(sql, params)
        if not ret:
            return 0
        return int(ret[0][0])

    def unsubmit(self, student):
        """ Undo the submission of an exam and reset the timer. """
        assert isinstance(exam, int)
        assert isinstance(student, int)
        reset_mark(exam, student)
        resetEndTime(exam, student)
        reset_submit_time(exam, student)
        set_user_status(student, exam, 1)
        touchUserExam(exam, student)

    def _serialize_examstruct(self):
        """ Serialize the exam structure for, eg. cache.
            The dates, especially, need work before JSON
        """
        FMT = '%Y-%m-%d %H:%M:%S'
        safe = exam.copy()
        safe['start'] = exam['start'].strftime(FMT)
        safe['end'] = exam['end'].strftime(FMT)

        return json.dumps(safe)

    @staticmethod
    def _deserialize_examstruct(obj):
        """ Deserialize a serialized exam structure. """

        FMT = '%Y-%m-%d %H:%M:%S'
        exam = json.loads(obj)
        exam['start'] = datetime.datetime.strptime(exam['start'], FMT)
        exam['end'] = datetime.datetime.strptime(exam['end'], FMT)

        return exam

    @property
    def active(self):
        return Util.is_now(self.start, self.end)

    @property
    def future(self):
        return Util.is_future(self.start)

    @property
    def past(self):
        return Util.is_past(self.end)

    @property
    def soon(self):
        return Util.is_soon(self.start)

    @property
    def recent(self):
        return Util.is_recent(self.end)


    # TODO: Optimize. This is called quite a lot
    def get_as_struct(self, user_id=None, include_qtemplates=False,
                        include_stats=False):
        """ Return a dictionary of useful data about the given exam for the user.
            Including stats is a performance hit so don't unless you need them.
        """

        sql = """SELECT "title", "owner", "type", "start", "end",
                        "description", "comments", "course", "archived",
                        "duration", "markstatus", "instant", "code"
                 FROM "exams" WHERE "exam" = %s LIMIT 1;"""
        params = (exam_id, )
        ret = run_sql(sql, params)
        if not ret:
            raise KeyError("Exam %s not found." % exam_id)
        row = ret[0]
        exam = {'id': exam_id,
                'title': row[0],
                'owner': row[1],
                'type': row[2],
                'start': row[3],
                'end': row[4],
                'instructions': row[5],
                'comments': row[6],
                'cid': row[7],
                'archived': row[8],
                'duration': row[9],
                'markstatus': row[10],
                'instant': row[11],
                'code': row[12]
        }

        course = Course.get(exam['cid'])


        exam['start_epoch'] = int(exam['start'].strftime("%s"))  # used to sort
        exam['period'] = General.human_dates(exam['start'], exam['end'])
        exam['course'] = course
        exam['start_human'] = exam['start'].strftime("%a %d %b")

        if include_qtemplates:
            exam['qtemplates'] = get_qts(exam_id)
            exam['num_questions'] = len(exam['qtemplates'])
        if include_stats:
            exam['coursedone'] = get_num_done(exam_id, exam['cid'])
            exam['notcoursedone'] = get_num_done(exam_id), exam['coursedone']
        if user_id:
            exam['is_done'] = is_done_by(user_id, exam_id)
            exam['can_preview'] = Permission.check_perm(user_id, exam['cid'], "exampreview")

        return exam

    def get_marks(self, group):
        """ Fetch the marks for a given user group.
        """
        sql = """
            SELECT u.id, q.qtemplate, q.score, q.firstview, q.marktime
            FROM users AS u,
                 questions AS q,
                 usergroups AS ug
            WHERE u.id = ug.userid
              AND ug.groupid = %s
              AND u.id = q.student
              AND q.exam = %s;
        """
        params = (group.id, exam_id)
        ret = DB.run_sql(sql, params)
        results = {}
        for row in ret:
            user_id = row[0]
            if not user_id in results:
                results[user_id] = {}
            qtemplate = row[1]
            results[user_id][qtemplate] = {
                'score': row[2],
                'firstview': row[3],
                'marktime': row[4]
            }

        return results

    def get_exam_q_by_pos_student(self, position, student):
        """ Return the question at the given position in the exam for the student.
            Return False if there is no question assigned yet.
        """
        ret = run_sql("""SELECT question FROM examquestions
                            WHERE student = %s
                            AND position = %s
                            AND exam = %s;""", (student, position, exam))
        if ret:
            return int(ret[0][0])
        return False

    def get_exam_q_by_qt_student(self, qt_id, student):
        """ Fetch an assessment question by student"""
        ret = run_sql("""SELECT question FROM questions
                            WHERE student=%s
                            AND qtemplate=%s
                            AND exam=%s;""", (student, qt_id, exam))
        if ret:
            return int(ret[0][0])
        return False

    def get_exam_qts_in_pos(self, position):
        """ Return the question templates in the given position in the exam, or 0.
        """
        ret = run_sql("""SELECT qtemplate
                         FROM examqtemplates
                         WHERE exam=%s
                           AND position=%s;""", (exam_id, position))
        if ret:
            qtemplates = [int(row[0]) for row in ret]
            return qtemplates
        return []

    def get_qt_exam_pos(self, qt_id):
        """Return the position a given question template holds in the exam"""
        ret = run_sql("""SELECT position
                         FROM examqtemplates
                         WHERE exam=%s
                           AND qtemplate=%s;""", (exam_id, qt_id))
        if ret:
            return int(ret[0][0])
        return None

    def update_exam_qt_in_pos(self, position, qtlist):
        """ Set the qtemplates at a given position in the exam to match
            the passed list. If we get qtlist = [0], we remove that position.
        """
        # First remove the current set
        run_sql("DELETE FROM examqtemplates "
                "WHERE exam=%s "
                "AND position=%s;", (exam_id, position))
        # Now insert the new set
        for alt in qtlist:
            if alt > 0:
                if isinstance(alt, int):  # might be '---'
                    run_sql("""INSERT INTO examqtemplates
                                    (exam, position, qtemplate)
                               VALUES (%s,%s,%s);""",
                                    (exam_id, position, alt))

    def add_exam_q(self, user, question, position):
        """Record that the student was assigned the given question for assessment.
        """
        sql = """SELECT id FROM examquestions
                  WHERE exam = %s
                  AND student = %s
                  AND position = %s
                  AND question = %s;"""
        params = (exam, user, position, question)
        ret = run_sql(sql, params)
        if ret:  # already exists
            return
        run_sql("INSERT INTO examquestions (exam, student, position, question) "
                "VALUES (%s, %s, %s, %s);",
                (exam, user, position, question))
        touch_user_exam(exam, user)

    def touch_user_exam(self, user_id):
        """ Update the lastchange field on a user exam so other places can tell that
            something changed. This should probably be done any time one of the
            following changes:
                userexam fields on that row
                question/guess in the exam changes
        """
        sql = "UPDATE userexams SET lastchange=NOW() WHERE exam=%s AND student=%s;"
        params = (exam_id, user_id)
        run_sql(sql, params)

    def remark_exam(self, student):
        """Re-mark the exam using the latest marking. """
        qtemplates = Exams.get_qts(exam)
        examtotal = 0.0
        end = Exams.get_mark_time(exam, student)
        for qtemplate in qtemplates:
            question = DB.get_exam_q_by_qt_student(exam, qtemplate, student)
            answers = DB.get_q_guesses_before_time(question, end)
            try:
                marks = mark_q(question, answers)
            except OaMarkerError:
                log(WARN,
                    "Marker Error, question %d while re-marking exam %s for student %s!" % (question, exam, student))
                marks = {}
            parts = [int(var[1:]) for var in marks.keys() if re.search("^A([0-9]+)$", var) > 0]
            parts.sort()
            total = 0.0
            for part in parts:
                if marks['C%d' % part] == 'Correct':
                    marks['C%d' % part] = "<b><font color='darkgreen'>Correct</font></b>"
                try:
                    mark = float(marks['M%d' % part])
                except (ValueError, TypeError, KeyError):
                    mark = 0
                total += mark
            DB.update_q_score(question, total)
            #        OaDB.setQuestionStatus(question, 3)    # 3 = marked
            examtotal += total
        Exams.save_score(exam, student, examtotal)
        return examtotal



# ----- Internal implementation details ------
# These are a bit messy so it's intended that they may go away one day
# Do not use directly, always go via Exam object.


class _Marklog(db.Model):

    __tablename__ = "marklog"
#CREATE TABLE marklog (
#    "id" SERIAL PRIMARY KEY,
#    "eventtime" timestamp without time zone,
#    "exam" integer REFERENCES exams("exam"),
#    "student" integer REFERENCES users("id"),
#    "marker" integer,
#    "operation" character varying(255),
#    "value" character varying(64)
#);

    id = Column(Integer, primary_key=True)
    eventtime = Column(DateTime)
    exam = Column(Integer, ForeignKey("exams.exam"))
    student = Column(Integer, ForeignKey("users.id"))
    marker = Column(Integer, ForeignKey("users.id"))
    operation = Column(String(255))
    value = Column(String(64))
#
#
#class _UserExam(db.Model):
#    __tablename__ = "userexams"
#    pass
#
#
#class _ExamTimer(db.Model):
#    __tablename__ = "examtimers"
##
##CREATE TABLE examtimers (
##    "id" SERIAL PRIMARY KEY,
##    "exam" integer NOT NULL,
##    "userid" integer NOT NULL,
##    "endtime" character varying(64)
##);
#    pass
#
#
#class _ExamQTemplate(db.Model):
#    __tablename__ = "examqtemplates"
#    pass
#
#
#class _ExamQuestion(db.Model):
#    __tablename__ = "examquestions"
#    pass
#
#
#
#
