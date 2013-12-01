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

