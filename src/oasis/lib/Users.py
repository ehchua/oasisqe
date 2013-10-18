# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Users.py
    Handle user related operations.
"""

from oasis.lib.DB import run_sql
from logging import log, WARN


def find(search, limit=20):
    """ return a list of user id's that reasonably match the search term.
        Search username then student ID then surname then first name.
        Return results in that order.
    """
    ret = run_sql("""SELECT id FROM users
                        WHERE LOWER(uname) LIKE LOWER(%s)
                        OR LOWER(familyname) LIKE LOWER(%s)
                        OR LOWER(givenname) LIKE LOWER(%s)
                        OR student_id LIKE %s
                        OR LOWER(email) LIKE LOWER(%s) LIMIT %s;""",
                  (search, search, search, search, search, limit))
    res = []
    if ret:
        res = [user[0] for user in ret]
    return res


def typeahead(search, limit=20):
    """ return a list of user id's that reasonably match the search term.
        Search username then student ID then surname then first name.
        Return results in that order.
    """
    ret = run_sql("""SELECT id
                     FROM users
                     WHERE
                         LOWER(uname) LIKE LOWER(%s)
                       OR
                         LOWER(email) LIKE LOWER(%s)
                     LIMIT %s;""",
                  (search, search, limit))
    res = []
    if ret:
        res = [user[0] for user in ret]
    return res


def get_groups(user):
    """ Return a list of groups the user is a member of.  """
    assert isinstance(user, int)
    ret = run_sql("""SELECT groupid FROM usergroups WHERE userid=%s;""",
                  (user,))
    if ret:
        groups = [int(row[0]) for row in ret]
        return groups
    log(WARN, "Request for unknown user or user in no groups.")
    return []


def get_courses(user_id):
    """ Return a list of the Course IDs of the courses the user is in """
    groups = get_groups(user_id)
    courses = []
    for group in groups:
        res = run_sql("""SELECT course
                         FROM groupcourses
                         WHERE groupid=%s LIMIT 1;""",
                      (group,))
        if res:
            course_id = int(res[0][0])
            courses.append(course_id)
    return courses

