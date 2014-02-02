# -*- coding: utf-8 -*-

""" Enrolment Feeds

    Support for importing enrolment data from elsewhere

    Used mainly by Groups
"""

from sqlalchemy import Column, Integer, String, Boolean, Text
import re
from oasis.database import Base


class UFeed(Base):
    """ A feed object tells us about the feed and where to get the scripts
        that do the main work of importing user account information
    """

    __tablename__ = "userfeeds"

# CREATE TABLE userfeeds (
#    "id" SERIAL PRIMARY KEY,
#    "name" character varying UNIQUE,
#    "title" character varying,
#    "script" character varying,
#    "envvar" character varying,
#    "freq" integer default 2,   -- 1 = hourly, 2 = daily, 3 = manually
#    "comments" text,
#    "priority" integer default 3,
#    "regex" character varying,
#    "status" character varying,
#    "error" character varying,
#    "active" boolean default False
#);

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True)
    title = Column(String(250))
    script = Column(String(250))
    envvar = Column(String(250))
    freq = Column(Integer)
    comments = Column(Text)
    priority = Column(Integer)
    regex = Column(String(250))
    status = Column(String(128))
    error = Column(String(250))
    active = Column(Boolean, default=False)

    def __init__(self, f_id=None, name=None,
                 title=None, script=None, envvar=None,
                 comments=None, freq=None, active=None,
                 priority=None, regex=None):
        """ If id is provided, load existing database
            record or raise KeyError. Otherwise create a new one.

            If rest is provided, create a new one. Raise KeyError if there's
            already an entry with the same name or code.
        """

        if not active:  # search
            if f_id:
                self._fetch_by_id(f_id)

        else:  # create new
            self.id = 0
            self.name = name
            self.title = title
            self.script = script
            self.envvar = envvar
            self.comments = comments
            self.freq = freq
            self.priority = priority
            self.regex = regex
            self.status = "new"
            self.error = ""
            self.active = active
            self.new = True

    def freq_name(self):
        """ Feed frequency as a human readable word.
        """

        if self.freq in ('1', 1):
            return "on login"
        if self.freq in ('2', 2):
            return "daily"
        if self.freq in ('3', 3):
            return "manual"
        return "unknown"

    def match_username(self, username):
        """ Is the feed willing to try and lookup this username.
            (Is the feed active and does the regex match)
        """

        if not self.regex:
            return True

        if re.match(self.regex, username):
            return True

        return False

    @staticmethod
    def get(feed_id):
        """ If an existing record exists with this id, load it and
            return.
        """
        return UFeed.query.filter_by(id=feed_id).first()

    @staticmethod
    def all_list():
        """
            Return a list of all user feeds in the system, sorted by priority
        """
        return UFeed.query.all()

    @staticmethod
    def active_hourly():
        """ Return a list of active hourly feeds.
        """
        return UFeed.query.filter_by(active=True, freq='1')

    @staticmethod
    def active_daily():
        """ Return a list of active daily feeds.
        """
        return UFeed.query.filter_by(active=True, freq='2')
