# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Question.py
    Handle Question (instance) related operations.
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from oasis import db
from oasis.models.QTemplate import QTemplate



class Question(db.Model):
    pass
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




def set_q_viewtime(question):
    """ Record that the question has been viewed.
        Not a good idea to call multiple times since it's
        nearly always the first time that we want.
    """
    run_sql("""UPDATE questions
               SET firstview=NOW()
               WHERE question=%s;""", (question,))


def set_q_marktime(question):
    """ Record that the question was marked.
        Probably best not to call multiple times since
        we usually want the first time.
    """
    run_sql("""UPDATE questions
               SET marktime=NOW()
               WHERE question=%s;""", (question,))


def get_q_viewtime(question):
    """ Return the time that the question was first viewed
        as a human readable string.
    """
    ret = run_sql("""SELECT firstview
                     FROM questions
                     WHERE question=%s;""", (question,))
    if ret:
        firstview = ret[0][0]
        if firstview:
            return firstview.strftime("%Y %b %d, %I:%M%P")
    return None


def get_q_marktime(question):
    """ Return the time that the question was marked
        as a human readable string, or None if it hasn't been.
    """
    ret = run_sql("""SELECT marktime
                     FROM questions
                     WHERE question=%s;""", (question,))
    if ret:
        marktime = ret[0][0]
        if marktime:
            return marktime.strftime("%Y %b %d, %I:%M%P")
    return None



def get_q_by_qt_student(qt_id, student):
    """ Fetch a question by student"""
    ret = run_sql("""SELECT question FROM questions
                        WHERE student = %s
                        AND qtemplate = %s and status = '1'
                        AND exam = '0'""", (student, qt_id))
    if ret:
        return int(ret[0][0])
    return False


def update_q_score(q_id, score):
    """ Set the score of a question."""
    try:
        sc = float(score)
    except (TypeError, ValueError):
        log(ERROR, "Unable to cast score to float!? '%s'" % score)
        return
    run_sql("""UPDATE questions SET score=%s WHERE question=%s;""",
            ("%.1f" % sc, q_id))


def set_q_status(q_id, status):
    """ Set the status of a question."""
    run_sql("UPDATE questions SET status=%s WHERE question=%s;", (status, q_id))


def get_q_version(q_id):
    """ Return the template version this question was generated from """
    ret = run_sql("SELECT version FROM questions WHERE question=%s;", (q_id,))
    if ret:
        return int(ret[0][0])
    return None


def get_q_variation(q_id):
    """ Return the template variation this question was generated from"""
    ret = run_sql("SELECT variation FROM questions WHERE question=%s;", (q_id,))
    if ret:
        return int(ret[0][0])
    return None


def get_q_parent(q_id):
    """ Return the template this question was generated from"""
    ret = run_sql("SELECT qtemplate FROM questions WHERE question=%s;", (q_id,))
    if ret:
        return int(ret[0][0])
    log(ERROR, "No parent found for question %s!" % q_id)
    return None



def create_q(qt_id, name, student, status, variation, version, exam):
    """ Add a question (instance) to the database."""
    conn = dbpool.begin()
    conn.run_sql("""INSERT INTO questions (qtemplate, name, student, status, variation, version, exam)
               VALUES (%s, %s, %s, %s, %s, %s, %s);""",
                 (qt_id, name, student, status, variation, version, exam ))
    res = conn.run_sql("SELECT currval('questions_question_seq')")
    dbpool.commit(conn)
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




def get_student_q_practice_stats(user_id, qt_id, num=3):
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
                    age = secs_to_human(age)
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


def get_q_stats_class(course, qt_id):
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




