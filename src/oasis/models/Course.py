# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Courses.py
    Handle course related operations.
"""

from logging import log, ERROR
import datetime

from oasis import db
from oasis.models.Group import Group
from oasis.models.Topic import Topic
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text


# WARNING: name and title are stored in the database as: title, description


class Course(db.Model):
    """ A topic contains a collection of questions.
    """
    __tablename__ = "courses"

#CREATE TABLE courses (
#    "course" SERIAL PRIMARY KEY,
#    "title" character varying(128) NOT NULL,
#    "description" text,
#    "owner" integer,
#    "active" integer DEFAULT 1,
#    "type" integer,
#    "practice_visibility" character varying DEFAULT 'all'::character varying,
#    "assess_visibility" character varying DEFAULT 'enrol'::character varying
#);

    id = Column("course", Integer, primary_key=True)
    name = Column("title", String(128), unique=True)
    title = Column("description", Text)
    owner = Column(Integer, ForeignKey('users.id'))
    active = Column(Boolean, default=True)
    type = Column(Integer)
    practice_visibility = Column(String(50), default="all")
    assess_visibility = Column(String(50), default="enrol")

    def get_users(self):
        """ Return a list of users in the course"""
        allusers = []
        for group in Group.active_by_course(self.id):
            allusers.append(group.members())
        return allusers

    def groups(self):
        """ Return a dict of groups currently attached to this course."""

        return Group.active_by_course(self.id)

    @staticmethod
    def all(only_active=True):
        """ Return a list of all courses in the system."""

        if only_active:
            return Course.query.order_by("title").filter_by(active=1)
        return Course.query.order_by("title").all()

    @staticmethod
    def all_dict():
        """ Return a summary of all courses, keyed by course id
        """

        courses = Course.all()
        coursedict = {}
        for course in courses:
            coursedict[course.id] = course

        return coursedict

    @staticmethod
    def get_by_name(name):
        """ Return a course object for the given name, or None
        """
        return Course.query.filter_by(name=name).first()

    @staticmethod
    def get(course_id):
        """ Return a course object for the given name, or None
        """
        return Course.query.filter_by(id=course_id).first()

    @staticmethod
    def create(name, title, owner, coursetype):
        """ Add a course to the database."""

        newc = Course()
        newc.name = name
        newc.title = title
        newc.owner = owner
        newc.type = coursetype

        db.session.add(newc)
        db.session.commit()
        return newc

    def add_group(self, group_id):
        """ Add a group to the course."""

        db.engine.execute("INSERT INTO groupcourses (groupid, course) VALUES (%s, %s);", (group_id, self.id))

    def del_group(self, group_id):
        """ Remove a group from the course."""

        db.engine.execute("DELETE FROM groupcourses WHERE groupid=%s AND course=%s;", (group_id, self.id))

    def topics(self, archived=2):
        """ Return a summary of all topics in the course.
            if archived=0, only return non archived courses
            if archived=1, only return archived courses
            if archived=2, return all courses
            if numq is true then include the number of questions in the topic
        """

        if archived == 0:
            return [t for t in Topic.by_course(self.id) if not t.archived]
        elif archived == 1:
            return [t for t in Topic.by_course(self.id) if t.archived]
        return [t for t in Topic.by_course(self.id)]

    def create_config_demonstration(self, period_id):
        """ Create any needed groups/configs for a demonstration course
        """
        # An ad-hoc Staff group
        name = "C_%s_STAFF_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group()

        group.name = name
        group.title = "%s, Staff" % (self.name,)
        group.gtype = 1  # staff
        group.source = "adhoc"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True

        db.session.add(group)
        db.session.commit()

        self.add_group(group.id)

        # An Open Registration student group
        name = "C_%s_OPEN_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group()

        group.name = name
        group.title = "%s, Students, Self Registered" % (self.name,)
        group.gtype = 2  # enrolment
        group.source = "open"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True

        db.session.add(group)
        db.session.commit()

        self.add_group(group.id)

        # An ad-hoc student group
        name = "C_%s_ADHOC_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group()

        group.name = name
        group.title = "%s, Students" % (self.name,)
        group.gtype = 2  # student
        group.source = "adhoc"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True
        db.session.add(group)
        db.session.commit()

        self.add_group(group.id)

    def create_config_casual(self, period_id):
        """ Create any needed groups/configs for a casual course
        """
        # An ad-hoc Staff group
        name = "C_%s_STAFF_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group.get(g_id=0)

        group.name = name
        group.title = "%s, Staff" % (self.name,)
        group.gtype = 1  # staff
        group.source = "adhoc"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True

        db.session.add(group)
        db.session.commit(group)

        self.add_group(group.id)

        # An ad-hoc student group
        name = "C_%s_ADHOC_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group()

        group.name = name
        group.title = "%s, Students" % (self.name,)
        group.gtype = 2  # student
        group.source = "adhoc"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True

        db.session.add(group)
        db.session.commit(group)

        self.add_group(group.id)

    def create_config_standard(self, period_id):
        """ Create any needed groups/configs for a standard course
        """

        # standard
        #    Create an adhoc staff group
        #           COURSE_name_STAFF_period
        #    Create a student group set to ad-hoc
        #           COURSE_name_ADHOC_period
        #    Create a student group set to (unconfigured) feed
        #           COURSE_name_feed_period

        # An ad-hoc Staff group
        name = "C_%s_STAFF_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group()

        group.name = name
        group.title = "%s, Staff" % (self.name,)
        group.gtype = 1  # staff
        group.source = "adhoc"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True

        db.session.add(group)
        db.session.commit()

        self.add_group(group.id)

        # An ad-hoc student group
        name = "C_%s_ADHOC_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group()

        group.name = name
        group.title = "%s, Students" % (self.name,)
        group.gtype = 2  # student
        group.source = "adhoc"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True

        db.session.add(group)
        db.session.commit()

        self.add_group(group.id)

    def create_config_large(self, period_id):
        """ Create any needed groups/configs for a large course
        """

        # large
        #    Create a staff group set to (unconfigured) feed
        #           COURSE_name_STAFF_feed_period
        #    Create an adhoc staff group
        #           COURSE_name_STAFF_period
        #    Create a student group set to ad-hoc
        #           COURSE_name_ADHOC_period
        #    Create a student group set to (unconfigured) feed
        #           COURSE_name_feed_period

        # An ad-hoc Staff group
        name = "C_%s_STAFF_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group()

        group.name = name
        group.title = "%s, Staff" % (self.name,)
        group.gtype = 1  # staff
        group.source = "adhoc"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True

        db.session.add(group)
        db.session.commit()

        self.add_group(group.id)

        # An ad-hoc student group
        name = "C_%s_STAFF_%s" % (self.name, period_id)
        group = Group.get_by_name(name)
        if not group:
            group = Group()

        group.name = name
        group.title = "%s, Students" % (self.name,)
        group.gtype = 2  # student
        group.source = "adhoc"
        group.period = period_id
        group.feed = None
        group.feedargs = ""
        group.active = True

        db.session.add(group)
        db.session.commit()

        self.add_group(group.id)

    def create_config(self, coursetemplate, period_id):
        """ Course is being created. Setup some configuration depending on
            given values.
        """

        # First, course template
        if coursetemplate == "demo":
            self.create_config_demonstration(period_id)
        elif coursetemplate == "casual":
            self.create_config_casual(period_id)
        elif coursetemplate == "standard":
            self.create_config_standard(period_id)
        elif coursetemplate == "large":
            self.create_config_large(period_id)

