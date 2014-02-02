# -*- coding: utf-8 -*-

""" Time Periods.

    Support for semesters/terms/etc.

    Used mainly by Groups
"""

import datetime
from sqlalchemy import Column, Integer, String, DateTime
from oasis.database import Base


class Period(Base):
    """ A time period is relatively simple, mainly just name and
        start and finish.
    """
    __tablename__ = "periods"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    title = Column(String(250))
    start = Column(DateTime)
    finish = Column(DateTime)
    code = Column(String(50))

    def historical(self):
        """ Is this period far enough in the past we can move it to "archive" or
            "historical" lists.
            Currently true if the finish date is more than a year in the past.
        """
        now = datetime.datetime.now().date()
        return self.finish.year < now.year - 1

    def editable(self):
        """ Can this time period be edited, or is it "built-in"
        """
        return not (self.id == 1)

    @staticmethod
    def fetch_by_name(name):
        """ If an existing record exists with this name, load it and
            return.
        """

        return Period.query.filter_by(name=name).first()

    @staticmethod
    def get(p_id):
        """ If an existing record exists with this id, load it and
            return.
        """
        return Period.query.filter_by(id=p_id).first()

    @staticmethod
    def fetch_by_code(code):
        """ If an existing record exists with this code, load it and
            return.
        """
        return Period.query.filter_by(code=code).first()

    @staticmethod
    def all_list():
        """ Return a list of all time periods in the system.
        """
        return Period.query.order_by("finish").all()
