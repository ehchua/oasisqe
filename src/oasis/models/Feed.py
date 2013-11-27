# -*- coding: utf-8 -*-

""" Enrolment Feeds

    Support for importing enrolment data from elsewhere

    Used mainly by Groups
"""

from oasis import db

from sqlalchemy import Column, Integer, String, Boolean


class Feed(db.Model):
    """ A feed object tells us about the feed and where to get the scripts
        that do the main work of importing.
    """
    __tablename__ = "feeds"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True)
    title = Column(String(250))
    script = Column(String(250))
    envvar = Column(String(250))
    comments = Column(String())
    freq = Column(Integer, default=2)
    status = Column(String(128))
    error = Column(String(250))
    active = Column(Boolean, default=False)

    def __init__(self, name=None, title=None, script=None, envvar=None,
                 comments=None, freq=None, active=None):
        """ If just id is provided, load existing database
            record or raise KeyError.

            If rest is provided, create a new one. Raise KeyError if there's
            already an entry with the same name or code.
        """

        self.id = 0
        self.name = name
        self.title = title
        self.script = script
        self.envvar = envvar
        self.comments = comments
        self.freq = freq
        self.status = "new"
        self.error = ""
        self.active = active
        self.new = True

    def freq_name(self):
        """ Feed frequency as a human readable word.
        """

        if self.freq in ('1', 1):
            return "hourly"
        if self.freq in ('2', 2):
            return "daily"
        if self.freq in ('3', 3):
            return "manual"
        return "unknown"

    @staticmethod
    def get(feed_id):
        """ If an existing record exists with this id, load it and
            return.
        """
        return Feed.query.filter_by(id=feed_id).first()

    @staticmethod
    def all_list():
        """ Return a list of all time periods in the system.
        """
        return Feed.query.all()

    @staticmethod
    def active_hourly():
        """ Return a list of active hourly feeds.
        """
        return Feed.query.filter_by(active=True, freq='1')

    @staticmethod
    def active_daily():
        """ Return a list of active daily feeds.
        """
        return Feed.query.filter_by(active=True, freq='2')
