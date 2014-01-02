# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" QTemplate.py
    Handle Question (template) related operations.
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey
from oasis import db
from logging import log, INFO, WARN, ERROR
import cPickle


class QTemplate(db.Model):

    __tablename__ = "qtemplates"
#
# CREATE TABLE qtemplates (
#     "qtemplate" SERIAL PRIMARY KEY,
#     "owner" integer REFERENCES users("id") NOT NULL,
#     "title" character varying(128) NOT NULL,
#     "description" text,
#     "marker" integer,
#     "scoremax" real,
#     "version" integer,
#     "status" integer,
#     "embed_id" character varying(16)
# );

    id = Column("qtemplate", Integer, primary_key=True)

    owner = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200))
    description = Column(String(250))
    marker = Column(Integer, ForeignKey("users.id"))
    scoremax = Column(Float, default=0)
    version = Column(Integer)
    status = Column(Integer)
    embed_id = Column(String(200))

    @staticmethod
    def get_by_embedid(embed_id):
        """ Find the question template with the given embed_id,
            or raise KeyError if not found.
        """

        if not embed_id:
            raise KeyError
        return QTemplate.query.filter_by(embed_id=embed_id).first()

    @staticmethod
    def get(qt_id, version=None):
        """ Return the numbered QTemplate. If no version give, return the most
            recent one. """

        if version:
            return QTemplate.query.filter_by(id=qt_id).order_by("-version").first()
        return QTemplate.query.filter_by(id=qt_id, version=version).first()

    @staticmethod
    def create(owner, title, desc, marker, scoremax, status):
        """ Create a new Question Template. """

        newqt = QTemplate()
        newqt.owner = owner
        newqt.title = title
        newqt.description = desc
        newqt.marker = marker
        newqt.scoremax = scoremax
        newqt.status = status

        db.session.add(newqt)
        db.session.commit()

        log(INFO, "QTemplate %s Created by %s" % (newqt.id, owner))

        return newqt


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
        attachments = [att[0] for att in ret]
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


class QuestionTopic(db.Model):
    """ Track a question's position in a topic.
    """

    __tablename__ = "questiontopics"
    #
    #CREATE TABLE questiontopics (
    #    "id" SERIAL PRIMARY KEY,
    #    "qtemplate" integer REFERENCES qtemplates("qtemplate") NOT NULL,
    #    "topic" integer REFERENCES topics("topic") NOT NULL,
    #    "position" integer
    #);
    id = Column(Integer, primary_key=True)
    qtemplate = Column(Integer, ForeignKey("qtemplates.qtemplate"))
    topic = Column(Integer, ForeignKey("topics.topic"))
    position = Column(Integer, default=0)



