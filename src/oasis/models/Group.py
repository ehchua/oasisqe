# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Group.py
    Handle group related operations.
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from oasis import db
from oasis.models.Period import Period


class GroupTypes(db.Model):
    """ Which types of group are there.
    """
    __tablename__ = "grouptypes"
    type = Column(Integer, primary_key=True)
    title = Column(String(128))
    description = Column(String(250))


class Group(db.Model):
    """ Look after groups of users.
    """
    __tablename__ = "ugroups"

    #CREATE TABLE ugroups (
    #    "id" SERIAL PRIMARY KEY,
    #    "name" character varying UNIQUE,
    #    "title" character varying,
    #    "gtype" integer references grouptypes("type"),
    #    "source" character varying DEFAULT 'adhoc'::character varying,
    #    "feed" integer references feeds("id") NULL,
    #    "period" integer references periods("id"),
    #    "feedargs" character varying DEFAULT '',
    #    "active" boolean default TRUE
    #);

    id = Column(Integer, primary_key=True)
    name = Column(String(20), unique=True)
    title = Column(String(250))
    gtype = Column(Integer, ForeignKey("grouptypes.type"))
    source = Column(String(250))
    feed = Column(Integer, ForeignKey("feeds.id"))
    period = Column(Integer, ForeignKey("periods.id"))
    feedargs = Column(String(250))
    active = Column(Boolean, default=True)

    _period_obj = None  #cache

    def __init__(self,
                 name=None,
                 title=None,
                 gtype=None,
                 source=None,
                 feed=None,
                 period=None,
                 feedargs=None,
                 active=None):
        """ If id is provided, load existing database
            record or raise KeyError.

            If gtype is provided, create a new one and raise KeyError if there's
            already an entry with the same name or code.
        """

        self.name = name
        self.title = title
        self.gtype = gtype
        self.active = active
        self.source = source
        self.period = period
        self._period_obj = None
        self.feed = feed
        self.feedargs = feedargs

    def members(self):
        """ Return a list of userids in the group. """
        res = db.engine.execute("SELECT userid FROM usergroups WHERE groupid=%s;", self.id)
        return [row[0] for row in res.fetchall()]

    def member_unames(self):
        """ Return a list of usernames in the group. """
        res = db.engine.execute("SELECT users.uname"
                                " FROM users,usergroups"
                                " WHERE usergroups.groupid=%s;", self.id)
        return [row[0] for row in res.fetchall()]

    def add_member(self, uid):
        """ Adds given user to the group."""
        if uid in self.members():
            return

        db.engine.execute("""INSERT INTO usergroups (userid, groupid)
               VALUES (%s, %s) """, (uid, self.id))

    def remove_member(self, uid):
        """ Remove given user from the group."""
        db.engine.execute("""DELETE FROM usergroups
               WHERE groupid=%s AND userid=%s;""", (self.id, uid))

    def flush_members(self):
        """ DANGEROUS:  Clears list of enrolled users in group.
            Use only just before importing new list.
        """
        db.engine.execute("""DELETE FROM usergroups WHERE groupid = %s;""", (self.id,))

    def size(self):
        """ How many people are in the group?
        """
        return len(self.members())

    def period_name(self):
        """ Human name for period
        """
        res = db.engine.execute("""SELECT name FROM periods WHERE id=%s;""", self.period)

        if not res:
            return 'unknown'
        return res.first()[0]

    def period_obj(self):
        """ Period object
        """
        if not self._period_obj:
            self._period_obj = Period.get(self.period)
        return self._period_obj

    # ------- Static Methods ----------
    @staticmethod
    def get(g_id):
        """ Find us by our id
        """
        return Group.query.filter_by(id=g_id).first()

    @staticmethod
    def get_by_feed(feed_id):
        """ Return a summary of all active or future groups with the given feed
        """

        return Group.query.filter_by(feed=feed_id)

    @staticmethod
    def get_by_period(period_id):
        """ Return a summary of all active or future groups with the given feed
        """
        return Group.query.filter_by(period=period_id, active=True)

    @staticmethod
    def get_by_name(name):
        """ Return (the first) group with the given name
        """
        return Group.query.filter_by(name=name).first()

    @staticmethod
    def all_groups():
        """ Return a summary of all groups
        """
        return Group.query.all()

    @staticmethod
    def enrolment_groups():
        """ Return a summary of all active enrolment groups
            Active means current or future
        """
        return Group.query.filter_by(gtype=2, active=True)
        #   TODO:          AND "periods"."finish" > NOW();""")  # gtype 2 =  enrolment

    @staticmethod
    def get_ids_by_name(name):
        """ Return any groups (list of ids) with the given name
        """

        res = db.engine.execute("""SELECT "id"
                 FROM "ugroups"
                 WHERE name=%s;""", name)
        return [row[0] for row in res.fetchall()]

    @staticmethod
    def active_by_course(course_id):
        """ Return a summary of all active or future groups with the given feed
        """

        res = db.engine.execute("""SELECT "ugroups"."id"
           FROM "ugroups", "groupcourses", "periods"
           WHERE "ugroups"."active" = TRUE
             AND "groupcourses"."groupid" = "ugroups"."id"
             AND "groupcourses"."course" = %s
             AND "ugroups"."period" = "periods"."id";""", course_id)
##TODO:            AND "periods"."finish" > NOW();""",

        return [Group.get(row[0]) for row in res.fetchall()]

    @staticmethod
    def groups_to_feed():
        """ Return list of all groups that are currently active and have an
            external feed. Active means current or future.
        """
        res = db.engine.execute("""SELECT "ugroups"."id"
                   FROM "ugroups", "periods"
                    WHERE  "ugroups"."active" = TRUE
                    AND "ugroups"."source" = 'feed'
                    AND "ugroups"."period" = "periods"."id"
                    AND "periods"."finish" > NOW();""")  # gtype 2 =  enrolment
        if not res:
            return {}

        groups = {}
        for row in res.fetchall():
            groups[row[0]] = Group.get(row[0])

        return groups

    @staticmethod
    def all_gtypes():
        """ Return a summary of all group types
        """
        res = db.engine.execute("""SELECT "type", "title", "description"
                                    FROM "grouptypes";""")
        return [{'type': int(row[0]),
                 'title': row[1],
                 'description': row[2]}
                for row in res.fetchall()]

