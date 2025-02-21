# -*- coding: utf-8 -*-

""" Time Periods.

    Support for semesters/terms/etc.

    Used mainly by Groups
"""

from ..lib.DB import run_sql, IntegrityError
from logging import getLogger
import datetime


L = getLogger("oasisqe")


class Period(object):
    """ A time period is relatively simple, mainly just name and
        start and finish.
    """

    def __init__(self, p_id=None, name=None,
                 title=None, start=None, finish=None,
                 code=None):
        """ If just id, name or code is provided, load existing database
            record or raise KeyError.

            If rest is provided, create a new one. Raise KeyError if there's
            already an entry with the same name or code.
        """

        if not start:  # search
            if p_id:
                self._fetch_by_id(p_id)
            elif name:
                self._fetch_by_name(name)
            elif code:
                self._fetch_by_code(code)

        else:  # create new
            self.id = 0
            self.name = name
            self.title = title
            self.start = start
            self.finish = finish
            self.code = code
            self.new = True

    def _fetch_by_name(self, name):
        """ If an existing record exists with this name, load it and
            return.
        """
        sql = """SELECT id, title, start, finish, code
                 FROM periods
                 WHERE name=%s;"""
        params = (name,)
        ret = run_sql(sql, params)
        if not ret:
            raise KeyError("Time Period with name '%s' not found" % name)

        self.name = name
        self.id = ret[0][0]
        self.title = ret[0][1]
        self.start = ret[0][2]
        self.finish = ret[0][3]
        self.code = ret[0][4]
        if not self.code:
            self.code = ""
        if not self.title:
            self.title = ""
        self.new = False

        return

    def _fetch_by_id(self, p_id):
        """ If an existing record exists with this id, load it and
            return.
        """
        sql = """SELECT name, title, start, finish, code
                 FROM periods
                 WHERE id=%s;"""
        params = (p_id,)
        ret = run_sql(sql, params)
        if not ret:
            raise KeyError("Time Period with id '%s' not found" % p_id)

        self.id = p_id
        self.name = ret[0][0]
        self.title = ret[0][1]
        self.start = ret[0][2]
        self.finish = ret[0][3]
        self.code = ret[0][4]
        self.new = False
        if not self.code:
            self.code = ""
        if not self.title:
            self.title = ""

        return

    def _fetch_by_code(self, code):
        """ If an existing record exists with this code, load it and
            return.
        """
        sql = """SELECT name, title, start, finish, id
                 FROM periods
                 WHERE code=%s;"""
        params = (code,)
        ret = run_sql(sql, params)
        if not ret:
            raise KeyError("Time Period with code '%s' not found" % code)

        self.code = code
        self.name = ret[0][0]
        self.title = ret[0][1]
        self.start = ret[0][2]
        self.finish = ret[0][3]
        self.id = ret[0][4]
        self.new = False

        return

    def save(self):
        """ Save ourselves back to database.
        """

        if self.code == "":
            dbcode = None  # "" would trip the uniqueness constraint
        else:
            dbcode = self.code
        if self.new:
            sql = """INSERT INTO periods ("name", "title", "start", "finish", "code")
                       VALUES (%s, %s, %s, %s,%s);"""
            params = (self.name, self.title, self.start, self.finish, dbcode)
            try:
                run_sql(sql, params)
            except IntegrityError:
                try:
                    exists = Period(name=self.name)
                except KeyError:
                    pass
                else:
                    if exists.id != self.id:
                        raise ValueError("Time Period with name already exists")

                try:
                    exists = Period(code=self.code)
                except KeyError:
                    pass
                else:
                    if exists.id != self.id:
                        raise ValueError("Time Period with code already exists")

            self.new = False
            return

        sql = """UPDATE periods
                 SET name=%s, title=%s, start=%s, finish=%s, code=%s
                 WHERE id=%s;"""
        params = (self.name, self.title, self.start, self.finish, dbcode,
                  self.id)
        try:
            run_sql(sql, params)
        except IntegrityError:
            try:
                exists = Period(name=self.name)
            except KeyError:
                pass
            else:
                if exists.id != self.id:
                    raise ValueError("Time Period with name already exists")

            try:
                exists = Period(code=self.code)
            except KeyError:
                pass
            else:
                if exists.id != self.id:
                    raise ValueError("Time Period with code already exists")

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

    # def delete(self):
    # def groups(self):


def all_list():
    """
        Return a list of all time periods in the system.
    """

    sql = """SELECT id, finish FROM periods order by finish;"""
    ret = run_sql(sql)
    if not ret:
        L.error('No time periods in Database? This should never happen.')
        return []

    periods = []
    for row in ret:
        p_id = row[0]
        periods.append(Period(p_id=p_id))

    return periods
