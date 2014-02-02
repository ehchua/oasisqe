# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Question.py
    Handle Question (instance) related operations.
"""

from logging import log, ERROR, INFO, WARN
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from oasis.lib import Util
import datetime
from oasis.database import Base


class Question(Base):

    __tablename__ = "questions"
##
#CREATE TABLE questions (
#    "question" SERIAL PRIMARY KEY,
#    "qtemplate" integer REFERENCES qtemplates("qtemplate"),
#    "status" integer,
#    "name" character varying(200),
#    "student" integer REFERENCES users("id"),
#    "score" real DEFAULT 0,
#    "firstview" timestamp,
#    "marktime" timestamp,
#    "variation" integer,
#    "version" integer,
#    "exam" integer
#);

    id = Column("question", Integer, primary_key=True)
    qtemplate = Column(Integer, ForeignKey("qtemplates.qtemplate"))
    status = Column(Integer)
    name = Column(String(200))
    student = Column(Integer, ForeignKey("users.id"))
    score = Column(Float, default=0)
    firstview = Column(DateTime)
    marktime = Column(DateTime)
    variation = Column(Integer)
    version = Column(Integer)
    exam = Column(Integer, default=0)

    @property
    def firstview_string(self):
        return self.firstview.strftime("%Y %b %d, %I:%M%P")

    @property
    def marktime_string(self):
        return self.marktime.strftime("%Y %b %d, %I:%M%P")

    def set_viewtime(self, when=None):
        """ Set the time the question was first viewed.
        """

        if not when:
            when = datetime.datetime.now()

        self.firstview = when
        db.session.add(self)
        db.session.commit()

    @staticmethod
    def get_by_qt_student(qt_id, student):
        """ Fetch a question by student"""

        return Question.query.filter_by(student=student, qtemplate=qt_id, status=1, exam=0).first()

    @staticmethod
    def get(qid):
        assert qid
        question = Question.query.filter_by(id=qid).first()
        if not question:
            raise KeyError
        return question

    @staticmethod
    def create_q(qt_id, name, student, status, variation, version, exam):
        """ Add a question (instance) to the database."""

        conn.run_sql("""INSERT INTO questions (qtemplate, name, student, status, variation, version, exam)
                   VALUES (%s, %s, %s, %s, %s, %s, %s);""",
                     (qt_id, name, student, status, variation, version, exam))
        res = conn.run_sql("SELECT currval('questions_question_seq')")

        if not res:
            log(ERROR,
                "CreateQuestion(%d, %s, %d, %s, %d, %d, %d) may have failed." % (
                    qt_id, name, student, status, variation, version, exam))
            return None
        return res[0][0]

    def get_student_q_practice_num(user_id, qt_id):
        """Return the number of times the given student has practiced the question
           Exclude assessed scores.
        """
        sql = """SELECT
                     COUNT(question)
                 FROM
                     questions
                 WHERE
                        qtemplate=%s
                     AND
                        student=%s
                     AND
                        status > 1
                     AND
                        exam < 1
                  GROUP BY qtemplate;
                  """
        params = (qt_id, user_id)

        ret = run_sql(sql, params)
        if ret:
            i = ret[0]
            num = int(i[0])
            return num
        else:
            return 0

    def get_student_q_practice_stats(self, user_id, qt_id, num=3):
        """Return data on the scores obtained while practicing the given question
           the last 'num' times. Exclude assessed scores. If num is not provided,
           defaults to 3. If num is 0, give stats for all.
           Returns list of last 'num' practices:
           {'score': score, 'question':question id, 'age': seconds since practiced }
           New Changes: set up a time period.
           It only shows the stats within 30 secs to 2 hrs.
        """
        sql = """SELECT
                     score, question, EXTRACT(epoch FROM (NOW() - marktime))
                 FROM questions
                 WHERE qtemplate=%s
                     AND student=%s
                     AND status > 1
                     AND exam < 1
                     AND marktime > '2005-07-16 00:00:00.00'
                     AND (marktime - firstview) > '00:00:20.00'
                     AND (marktime - firstview) < '02:00:01.00'
                 ORDER BY marktime DESC"""
        params = (qt_id, user_id)
        if num > 0:
            sql += " LIMIT '%d'" % num
        sql += ";"
        ret = run_sql(sql, params)
        stats = []
        if ret:
            for row in ret:
                ageseconds = 10000000000  # could be from before we tracked it.
                age = row[2]
                try:
                    age = int(age)
                    ageseconds = age
                    if age > 63000000:    # more than two years
                        age = "more than 2 years"
                    else:
                        age = Util.secs_to_human(age)
                except (TypeError, ValueError):
                    age = "more than 2 years"
                stats.append({
                    'score': float(row[0]),
                    'question': int(row[1]),
                    'age': age,
                    'ageseconds': ageseconds
                })

            return stats[::-1]   # reverse it so they're in time order
        return None

    def get_q_stats_class(self, course, qt_id):
        """Fetch a bunch of statistics about the given question for the class
        """
        sql = """SELECT COUNT(question),
                        AVG(score),
                        STDDEV(score),
                        MAX(score),
                        MIN(score)
                 FROM questions
                 WHERE qtemplate = %s
                 AND marktime < NOW()
                 AND (marktime - firstview) > '00:00:20'
                 AND (marktime - firstview) < '02:00:01'
                 AND student IN
                    (SELECT userid FROM usergroups WHERE groupid IN
                      (SELECT groupid FROM groupcourses WHERE course = %s)
                 );
              """
        params = (qt_id, course)
        ret = run_sql(sql, params)
        if ret:
            i = ret[0]
            if i[1]:
                if i[2]:
                    stats = {'count': int(i[0]),
                             'avg': float(i[1]),
                             'stddev': float(i[2]),
                             'max': float(i[3]),
                             'min': float(i[4])}
                else:   # empty stddev from e.g. only 1 count
                    stats = {'count': int(i[0]),
                             'avg': float(i[1]),
                             'stddev': 0.0,
                             'max': float(i[3]),
                             'min': float(i[4])}
                return stats


def get_q_att(qt_id, name, variation, version=1000000000):
    """ Fetch an attachment for the question"""
    if version == 1000000000:
        version = get_qt_version(qt_id)
    key = "questionattach/%d/%s/%d/%d" % (qt_id, name, variation, version)
    (value, found) = fileCache.get(key)
    if not found:
        ret = run_sql("""SELECT qtemplate, data
                            FROM qattach
                            WHERE qtemplate=%s
                            AND name=%s
                            AND variation=%s
                            AND version=%s;""",
                      (qt_id, name, variation, version))
        if ret:
            data = str(ret[0][1])
            fileCache.set(key, data)
            return data
        fileCache.set(key, False)
        return get_qt_att(qt_id, name, version)
    return value


def create_q_att(qt_id, variation, name, mimetype, data, version):
    """ Create a new Question Attachment using given data."""
    safedata = psycopg2.Binary(data)
    run_sql("""INSERT INTO qattach (qtemplate, variation, mimetype, name, data, version)
               VALUES (%s, %s, %s, %s, %s, %s);""",
               (qt_id, variation, mimetype, name, safedata, version))


def save_guess(q_id, part, value):
    """ Store the guess in the database."""
    # noinspection PyComparisonWithNone
    if not value is None:  # "" is legit
        run_sql("""INSERT INTO guesses (question, created, part, guess)
                   VALUES (%s, NOW(), %s, %s);""", (q_id, part, value))


def get_q_guesses(q_id):
    """ Return a dictionary of the recent guesses in a question."""
    ret = run_sql("""SELECT part, guess
                     FROM guesses
                     WHERE question = %s
                     ORDER BY created DESC;""", (q_id,))
    if not ret:
        return {}
    guesses = {}
    for row in ret:
        if not "G%d" % (int(row[0])) in guesses:
            guesses["G%d" % (int(row[0]))] = row[1]
    return guesses


def get_q_guesses_before_time(q_id, lasttime):
    """ Return a dictionary of the recent guesses in a question,
        from before it was marked.
    """
    ret = run_sql("""SELECT part, guess
                     FROM guesses
                     WHERE question=%s
                       AND created < %s
                     ORDER BY created DESC;""",
                     (q_id, lasttime))
    if not ret:
        return {}
    guesses = {}
    for row in ret:
        if not "G%d" % (int(row[0])) in guesses:
            guesses["G%d" % (int(row[0]))] = row[1]
    return guesses
