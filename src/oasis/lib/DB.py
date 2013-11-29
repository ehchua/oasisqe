# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" OaDB.py
    This provides a collection of methods for accessing the database.
    If the database is changed to something other than postgres, this
    is where to start. Since this has grown so large, parts of it are
    being broken off and put in db/*.py
"""

import psycopg2
import cPickle
import datetime
import json

from logging import log, INFO, WARN, ERROR

IntegrityError = psycopg2.IntegrityError

# Global dbpool
import OaConfig
import Pool

# 3 connections. Lets us keep going if one is slow but
# doesn't overload the server if there're a lot of us
dbpool = Pool.DbPool(OaConfig.oasisdbconnectstring, 3)

# Cache stuff on local drives to save our poor database
fileCache = Pool.fileCache(OaConfig.cachedir)


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


def get_qt_by_embedid(embed_id):
    """ Find the question template with the given embed_id,
        or raise KeyError if not found.
    """
    sql = "SELECT qtemplate FROM qtemplates WHERE embed_id=%s LIMIT 1;"
    params = (embed_id,)
    ret = run_sql(sql, params)
    if not ret:
        raise KeyError("Can't find qtemplate with embed_id = %s" % embed_id)
    row = ret[0]
    qtemplate = int(row[0])
    return qtemplate


def get_qtemplate(qt_id, version=None):
    """ Return a dictionary with the QTemplate information """
    if version:
        sql = """SELECT qtemplate, owner, title, description,
                        marker, scoremax, version, status, embed_id
                 FROM qtemplates
                 WHERE qtemplate=%s
                   AND version=%s;"""
        params = (qt_id, version)
    else:
        sql = """SELECT qtemplate, owner, title, description,
                        marker, scoremax, version, status, embed_id
                 FROM qtemplates
                 WHERE qtemplate=%s
                 ORDER BY version DESC
                 LIMIT 1;"""
        params = (qt_id,)
    ret = run_sql(sql, params)
    if len(ret) == 0:
        raise KeyError("Can't find qtemplate %s, version %s" % (qt_id, version))
    row = ret[0]
    qtemplate = {
        'id': int(row[0]),
        'owner': int(row[1]),
        'title': row[2],
        'description': row[3],
        'marker': row[4],
        'scoremax': row[5],
        'version': int(row[6]),
        'status': int(row[7]),
        'embed_id': row[8]
    }
    if not qtemplate['embed_id']:
        qtemplate['embed_id'] = ""
    try:
        qtemplate['scoremax'] = float(qtemplate['scoremax'])
    except TypeError:
        qtemplate['scoremax'] = None
    return qtemplate


def update_qt_embedid(qt_id, embed_id):
    """ Set the QTemplate's embed_id"""
    if embed_id == "":
        embed_id = None
    sql = "UPDATE qtemplates SET embed_id=%s WHERE qtemplate=%s"
    params = (embed_id, qt_id)
    if run_sql(sql, params) is False:  # could be [], which is success
        return False
    return True


def incr_qt_version(qt_id):
    """ Increase the version number of the current question template"""
    # FIXME: Not done in a parallel-safe manner. Could find a way to do this
    # in the database. Fairly low risk.
    version = int(get_qt_version(qt_id))
    version += 1
    run_sql("""UPDATE qtemplates
               SET version=%s
               WHERE qtemplate=%s;""", (version, qt_id))
    return version


def get_qt_version(qt_id):
    """ Fetch the version of a question template."""
    ret = run_sql("""SELECT version
                     FROM qtemplates
                     WHERE qtemplate=%s;""", (qt_id,))
    if ret:
        return int(ret[0][0])
    log(WARN, "Request for unknown question template %s." % qt_id)


def get_qt_maxscore(qt_id):
    """ Fetch the maximum score of a question template."""
    key = "qtemplate-%d-maxscore" % (qt_id,)
    ret = run_sql("""SELECT scoremax
                     FROM qtemplates
                     WHERE qtemplate=%s;""", (qt_id,))
    if ret:
        try:
            scoremax = float(ret[0][0])
        except (ValueError, TypeError, KeyError):
            scoremax = 0.0
        return scoremax
    log(WARN, "Request for unknown question template %s." % qt_id)


def get_qt_marker(qt_id):
    """ Fetch the marker of a question template."""
    ret = run_sql("SELECT marker FROM qtemplates WHERE qtemplate=%s;", (qt_id,))
    if ret:
        return int(ret[0][0])
    log(WARN, "Request for unknown question template %s." % qt_id)


def get_qt_owner(qt_id):
    """ Fetch the owner of a question template.
        (The last person to make changes to it)
    """
    ret = run_sql("SELECT owner FROM qtemplates WHERE qtemplate=%s;", (qt_id,))
    if ret:
        return ret[0][0]
    log(WARN, "Request for unknown question template %s." % qt_id)


def get_qt_name(qt_id):
    """ Fetch the name of a question template."""
    ret = run_sql("SELECT title FROM qtemplates WHERE qtemplate=%s;", (qt_id,))
    if ret:
        return ret[0][0]
    log(WARN, "Request for unknown question template %s." % qt_id)


def get_qt_embedid(qt_id):
    """ Fetch the embed_id of a question template."""
    ret = run_sql("""SELECT embed_id
                     FROM qtemplates
                     WHERE qtemplate=%s;""", (qt_id,))
    if ret:
        embed_id = ret[0][0]
        if not embed_id:
            embed_id = ""
        return embed_id
    log(WARN, "Request for unknown question template %s." % qt_id)


def get_qt_atts(qt_id, version=1000000000):
    """ Return a list of (names of) all attachments connected to
        this question template.
    """
    if version == 1000000000:
        version = get_qt_version(qt_id)
    ret = run_sql("SELECT name FROM qtattach WHERE qtemplate = %s "
                  "AND version <= %s GROUP BY name ORDER BY name;",
                  (qt_id, version))
    if ret:
        attachments = [att[0] for att in ret if att[0] not in att and att[0]]
        return attachments
    return []


def get_q_att_mimetype(qt_id, name, variation, version=1000000000):
    """ Return a string containing the mime type of the attachment.
    """
    if version == 1000000000:
        version = get_qt_version(qt_id)
    try:
        key = "questionattach/%d/%s/%d/%d/mimetype" % \
              (qt_id, name, variation, version)
        (value, found) = fileCache.get(key)
        if not found:
            ret = run_sql("""SELECT qtemplate, mimetype
                                FROM qattach
                                WHERE name=%s
                                AND qtemplate=%s
                                AND variation=%s
                                AND version=%s
                                """, (name, qt_id, variation, version))
            if ret:
                data = ret[0][1]
                fileCache.set(key, data)
                return data
                # We use mimetype to see if an attachment is generated so
                # not finding one is no big deal.
            return False
        return value
    except BaseException, err:
        log(WARN,
            "%s args=(%s,%s,%s,%s)" % (err, qt_id, name, variation, version))
    return False


def get_qt_att_mimetype(qt_id, name, version=1000000000):
    """ Fetch the mime type of a template attachment.
        If version is set to 0, will fetch the newest.
    """
    if version == 1000000000:
        version = get_qt_version(qt_id)
    key = "qtemplateattach/%d/%s/%d/mimetype" % (qt_id, name, version)
    (value, found) = fileCache.get(key)
    if not found:
        nameparts = name.split("?")
        if len(nameparts) > 1:
            name = nameparts[0]
        ret = run_sql("""SELECT mimetype
                            FROM qtattach
                            WHERE qtemplate = %s
                            AND name = %s
                            AND version = (SELECT MAX(version)
                                FROM qtattach
                                WHERE qtemplate=%s
                                AND version <= %s
                                AND name=%s)""",
                      (qt_id, name, qt_id, version, name))
        if ret:
            data = ret[0][0]
            fileCache.set(key, data)
            return data
        return False
    return value


def get_q_att_fname(qt_id, name, variation, version=1000000000):
    """ Fetch the on-disk filename where the attachment is stored.
        This may have to fetch it from the database.
        The intent is to save time by passing around a filename rather than the
        entire attachment.
    """
    if version == 1000000000:
        version = get_qt_version(qt_id)
    key = "questionattach/%d/%s/%d/%d" % (qt_id, name, variation, version)
    (filename, found) = fileCache.getFilename(key)
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
            (filename, found) = fileCache.getFilename(key)
            if found:
                return filename
        fileCache.set(key, False)
        return False
    return filename


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


def get_qt_att_fname(qt_id, name, version=1000000000):
    """ Fetch a filename for the attachment in the question template.
        If version is set to 0, will fetch the newest.
    """
    if version == 1000000000:
        version = get_qt_version(qt_id)
    key = "qtemplateattach/%d/%s/%d" % (qt_id, name, version)
    (filename, found) = fileCache.getFilename(key)
    if (not found) or version == 1000000000:
        ret = run_sql("""SELECT data
                         FROM qtattach
                         WHERE qtemplate = %s
                           AND name = %s
                           AND version =
                             (SELECT MAX(version)
                              FROM qtattach
                              WHERE qtemplate=%s
                                AND version <= %s
                                AND name=%s);""",
                      (qt_id, name, qt_id, version, name))
        if ret:
            data = str(ret[0][0])
            fileCache.set(key, data)
            (filename, found) = fileCache.getFilename(key)
            if found:
                return filename
        fileCache.set(key, False)
        return False
    return filename


def get_qt_att(qt_id, name, version=1000000000):
    """ Fetch an attachment for the question template.
        If version is set to 0, will fetch the newest.
    """
    if version == 1000000000:
        version = get_qt_version(qt_id)
    key = "qtemplateattach/%d/%s/%d" % (qt_id, name, version)
    (value, found) = fileCache.get(key)
    if (not found) or version == 1000000000:
        ret = run_sql("""SELECT data
                         FROM qtattach
                         WHERE qtemplate = %s
                           AND name = %s
                           AND version =
                             (SELECT MAX(version)
                              FROM qtattach
                              WHERE qtemplate=%s
                                AND version <= %s
                                AND name=%s);""",
                      (qt_id, name, qt_id, version, name))
        if ret:
            data = str(ret[0][0])
            fileCache.set(key, data)
            return data
        fileCache.set(key, False)
        return False
    return value


def get_qtemplate_topic_pos(qt_id, topic_id):
    """ Fetch the position of a question template in a topic. """
    ret = run_sql("""SELECT position
                     FROM questiontopics
                     WHERE qtemplate=%s AND topic=%s;""", (qt_id, topic_id))
    if ret:
        return int(ret[0][0])
    return False


def get_qt_max_pos_in_topic(topic_id):
    """ Fetch the maximum position of a question template in a topic."""
    res = run_sql("""SELECT MAX(position)
                     FROM questiontopics
                     WHERE topic=%s;""", (topic_id,))
    if not res:
        return 0
    return res[0][0]


def get_qt_variations(qt_id, version=1000000000):
    """ Return all variations of a question template."""
    if version == 1000000000:
        version = get_qt_version(qt_id)
    ret = {}
    res = run_sql("""SELECT variation, data
                     FROM qtvariations
                     WHERE qtemplate=%s
                       AND version =
                         (SELECT MAX(version)
                          FROM qtvariations
                          WHERE qtemplate=%s
                            AND version <= %s)""", (qt_id, qt_id, version))
    if not res:
        log(WARN,
            "No Variation found for qtid=%d, version=%d" % (qt_id, version))
        return []
    for row in res:
        result = str(row[1])
        ret[row[0]] = cPickle.loads(result)
    return ret


def get_qt_variation(qt_id, variation, version=1000000000):
    """ Return a specific variation of a question template."""
    if version == 1000000000:
        version = get_qt_version(qt_id)
    res = run_sql("""SELECT data
                     FROM qtvariations
                     WHERE qtemplate=%s
                       AND variation=%s
                       AND version =
                         (SELECT MAX(version)
                          FROM qtvariations
                          WHERE qtemplate=%s
                            AND version <= %s);""",
                     (qt_id, variation, qt_id, version))
    if not res:
        log(WARN,
            "Request for unknown qt variation. (%d, %d, %d)" %
            (qt_id, variation, version))
        return None
    result = None
    data = None
    try:
        result = str(res[0][0])
        data = cPickle.loads(result)
    except TypeError:
        log(WARN,
            "Type error trying to cpickle.loads(%s) for (%s, %s, %s)" %
            (type(result), qt_id, variation, version))
    return data


def get_qt_num_variations(qt_id, version=1000000000):
    """ Return the number of variations for a question template. """
    if version == 1000000000:
        version = get_qt_version(qt_id)
    ret = run_sql("""SELECT MAX(variation) FROM qtvariations
                        WHERE qtemplate=%s AND version = (
                         SELECT MAX(version) FROM qtvariations
                             WHERE qtemplate=%s AND version <= %s)""",
                  (qt_id, qt_id, int(version)))
    try:
        num = int(ret[0][0])
    except BaseException, err:
        log(WARN,
            "No Variation found for qtid=%d, version=%d: %s" %
            (qt_id, version, err))
        return 0
    return num


def create_q_att(qt_id, variation, name, mimetype, data, version):
    """ Create a new Question Attachment using given data."""
    safedata = psycopg2.Binary(data)
    run_sql("""INSERT INTO qattach (qtemplate, variation, mimetype, name, data, version)
               VALUES (%s, %s, %s, %s, %s, %s);""",
               (qt_id, variation, mimetype, name, safedata, version))


def create_qt_att(qt_id, name, mimetype, data, version):
    """ Create a new Question Template Attachment using given data."""
    if not data:
        data = ""
    if isinstance(data, unicode):
        data = data.encode("utf8")
    safedata = psycopg2.Binary(data)
    run_sql("""INSERT INTO qtattach (qtemplate, mimetype, name, data, version)
               VALUES (%s, %s, %s, %s, %s);""",
               (qt_id, mimetype, name, safedata, version))
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


def update_qt_title(qt_id, title):
    """ Update the title of a question template. """
    sql = "UPDATE qtemplates SET title = %s WHERE qtemplate = %s;"
    params = (title, qt_id)
    run_sql(sql, params)


def update_qt_owner(qt_id, owner):
    """ Update the owner of a question template.
        Generally we say the owner is the last person to alter the qtemplate.
    """
    sql = "UPDATE qtemplates SET owner = %s WHERE qtemplate = %s;"
    params = (owner, qt_id)
    run_sql(sql, params)


def update_qt_maxscore(qt_id, scoremax):
    """ Update the maximum score of a question template. """
    sql = """UPDATE qtemplates SET scoremax=%s WHERE qtemplate=%s;"""
    params = (scoremax, qt_id)
    run_sql(sql, params)


def update_qt_marker(qt_id, marker):
    """ Update the marker of a question template."""
    sql = """UPDATE qtemplates
             SET marker=%s
             WHERE qtemplate=%s;"""
    params = (marker, qt_id)
    run_sql(sql, params)


def update_qt_pos(qt_id, topic_id, position):
    """ Update the position a question template holds in a topic."""
    previous = get_qtemplate_topic_pos(qt_id, topic_id)
    sql = """UPDATE questiontopics
             SET position=%s
             WHERE topic=%s
             AND qtemplate=%s;"""
    params = (position, topic_id, qt_id)
    if not previous is False:
        run_sql(sql, params)
    else:
        add_qt_to_topic(qt_id, topic_id, position)


def move_qt_to_topic(qt_id, topic_id):
    """ Move a question template to a different sub category."""
    run_sql("""UPDATE questiontopics
         SET topic=%s WHERE qtemplate=%s;""", (topic_id, qt_id))


def add_qt_to_topic(qt_id, topic_id, position=0):
    """ Put the question template into the topic."""
    run_sql("INSERT INTO questiontopics (qtemplate, topic, position) "
            "VALUES (%s, %s, %s)", (qt_id, topic_id, position))


def copy_qt_all(qt_id):
    """ Make an identical copy of a question template,
        including all attachments.
    """
    newid = copy_qt(qt_id)
    if newid <= 0:
        return 0
    attachments = get_qt_atts(qt_id)
    newversion = get_qt_version(newid)
    for name in attachments:
        create_qt_att(newid,
                      name,
                      get_qt_att_mimetype(qt_id, name),
                      get_qt_att(qt_id, name),
                      newversion)
    try:
        variations = get_qt_variations(qt_id)
        for variation in variations.keys():
            add_qt_variation(newid,
                             variation,
                             variations[variation],
                             newversion)
    except AttributeError, err:
        log(WARN,
            "Copying a qtemplate %s with no variations. '%s'" %
            (qt_id, err))
    return newid


def copy_qt(qt_id):
    """ Make an identical copy of a question template entry.
        Returns the new qtemplate id.
    """
    res = run_sql("SELECT owner, title, description, marker, scoremax, status "
                  "FROM qtemplates "
                  "WHERE qtemplate = %s",
                  (qt_id,))
    if not res:
        raise KeyError("QTemplate %d not found" % qt_id)
    orig = res[0]
    newid = create_qt(
        int(orig[0]),
        orig[1],
        orig[2],
        orig[3],
        orig[4],
        int(orig[5])
    )
    if newid <= 0:
        raise IOError("Unable to create copy of QTemplate %d" % qt_id)
    return newid


def add_qt_variation(qt_id, variation, data, version):
    """ Add a variation to the question template. """
    pick = cPickle.dumps(data)
    safedata = psycopg2.Binary(pick)
    run_sql("INSERT INTO qtvariations (qtemplate, variation, data, version) "
            "VALUES (%s, %s, %s, %s)",
            (qt_id, variation, safedata, version))


def create_qt(owner, title, desc, marker, scoremax, status):
    """ Create a new Question Template. """
    conn = dbpool.begin()
    conn.run_sql("INSERT INTO qtemplates (owner, title, description, marker, scoremax, status, version) "
                 "VALUES (%s, %s, %s, %s, %s, %s, 2);",
                 (owner, title, desc, marker, scoremax, status))
    res = conn.run_sql("SELECT currval('qtemplates_qtemplate_seq')")
    dbpool.commit(conn)
    if res:
        return int(res[0][0])
    log(ERROR,
        "create_qt error (%d, %s, %s, %d, %s, %s)" %
        (owner, title, desc, marker, scoremax, status))


def _serialize_courseexaminfo(info):
    """ Serialize the structure for, eg. cache.
        The dates, especially, need work before JSON
    """
    FMT = '%Y-%m-%d %H:%M:%S'
    safe = {}
    for k, exam in info.iteritems():
        safe[k] = exam
        safe[k]['start'] = exam['start'].strftime(FMT)
        safe[k]['end'] = exam['end'].strftime(FMT)
    return json.dumps(safe)


def _deserialize_courseexaminfo(obj):
    """ Deserialize a serialized exam info structure."""
    FMT = '%Y-%m-%d %H:%M:%S'
    safe = json.loads(obj)
    info = {}
    for k, exam in safe.iteritems():
        info[k] = exam
        info[k]['start'] = datetime.datetime.strptime(exam['start'], FMT)
        info[k]['end'] = datetime.datetime.strptime(exam['end'], FMT)
    return info


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


def secs_to_human(seconds):
    """Convert a number of seconds to a human readable string, eg  "8 days"
    """
    perday = 86400
    return "%d days ago" % int(seconds / perday)


def get_prac_stats_user_qt(user_id, qt_id):
    """ Return Data on the scores of individual practices. it is used to
        display Individual Practise Data section
        Restricted by a certain time period which is 30 secs to 2 hours"""
    sql = """SELECT COUNT(question),MAX(score),MIN(score),AVG(score)
             FROM questions WHERE qtemplate = %s AND student = %s;"""
    params = (qt_id, user_id)
    ret = run_sql(sql, params)
    if ret:
        i = ret[0]
        if i[0]:
            stats = {'num': int(i[0]),
                     'max': float(i[1]),
                     'min': float(i[2]),
                     'avg': float(i[3])}
            return stats
    return None


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


def get_qt_editor(qt_id):
    """ Return which type of editor the question should use.
        OQE | Raw
    """
    etype = "Raw"
    atts = get_qt_atts(qt_id)
    for att in atts:
        if att.endswith(".oqe"):
            etype = "OQE"
    return etype


def get_db_version():
    """ Return an string representing the database version
        If it's too old to have a configuration field, then use some heuristics.
    """

    # We have a setting, easy
    try:
        ret = run_sql("""SELECT "value"
                         FROM config
                         WHERE "name" = 'dbversion';""", quiet=True)
        if ret:
            return ret[0][0]
    except psycopg2.DatabaseError:
        pass

    # We don't have a setting, need to figure it out
    try:  # questionflags was removed for 3.9.1
        ret = run_sql("SELECT 1 FROM questionflags;", quiet=True)
        if isinstance(ret, list):
            return "3.6"

    except psycopg2.DatabaseError:
        pass

    try:  # one of the very original fields
        ret = run_sql("""SELECT 1 from users;""")
        if ret:
            return "3.9.1"
    except psycopg2.DatabaseError:
        pass

    # No database at all?
    return "unknown"


def get_db_size():
    """ Find out how much space the DB is taking
        Return as a list of  [  [tablename, size] , ... ]
    """

    # Query from   http://wiki.postgresql.org/wiki/Disk_Usage
    sql = """SELECT nspname || '.' || relname AS "relation",
                    pg_size_pretty(pg_total_relation_size(C.oid)) AS "total_size"
             FROM pg_class C
             LEFT JOIN pg_namespace N ON (N.oid = C.relnamespace)
             WHERE nspname NOT IN ('pg_catalog', 'information_schema')
               AND C.relkind <> 'i'
               AND nspname !~ '^pg_toast'
             ORDER BY pg_total_relation_size(C.oid) DESC
             LIMIT 10;
    """

    ret = run_sql(sql)
    sizes = []
    for row in ret:
        sizes.append([row[0], row[1]])

    return sizes

