# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Contains db access functions for users, groups, permissions and courses """

from oasis import db
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text

PERMS = {'sysadmin': 1, 'useradmin': 2,
         'courseadmin': 3, 'coursecoord': 4,
         'questionedit': 5, 'viewmarks': 8,
         'altermarks': 9, 'questionpreview': 10,
         'exampreview': 11, 'examcreate': 14,
         'memberview': 15, 'surveypreview': 16,
         'surveycreate': 17, 'sysmesg': 18,
         'syscourses': 19, 'surveyresults': 20}


class Permission(db.Model):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("users.id"))
    permission = Column(Integer)
    course = Column(Integer, ForeignKey("courses.course"))

    @staticmethod
    def check_perm(user_id, group_id, perm):
        """ Check to see if the user has the permission on the given course. """
        permission = 0
        if not isinstance(perm, int):  # we have a string name so look it up
            if perm in PERMS:
                permission = PERMS[perm]

        # If they're superuser, let em do anything
        if Permission.query.filter_by(userid=user_id, permission=1):
            return True

        # If we're asking for course -1 it means any course will do.
        if group_id == -1 and Permission.query.filter_by(userid=user_id, permission=permission):
            return True

        # Do they have the permission explicitly?
        if Permission.query.filter_by(userid=user_id, permission=permission, course_id=group_id):
            return True

        # Now check for global override
        if Permission.query.filter_by(userid=user_id, permission=0, course_id=group_id):
            return True
        return False

    @staticmethod
    def satisfy_perms(uid, group_id, permlist):
        """ Does the user have one or more of the permissions in permlist,
            on the given group?
        """
        for perm in permlist:
            if Permission.check_perm(uid, group_id, perm):
                return True
        return False

    @staticmethod
    def delete_perm(uid, group_id, perm):
        """Remove a permission. """
        db.engine.execute("""DELETE FROM permissions
                   WHERE userid=%s
                     AND course=%s
                     AND permission=%s""",
                (uid, group_id, perm))

    @staticmethod
    def add_perm(uid, course_id, perm):
        """ Assign a permission."""
        db.insert("permissions", values={'course': course_id, 'userid': uid, 'permission': perm})

    @staticmethod
    def get_course_perms(course_id):
        """ Return a list of all users with permissions on the given course.
            Exclude those who get them via superuser.
        """
        ret = db.engine.execute("""SELECT id, userid, permission
                         FROM permissions
                         WHERE course=%s;""",
                      (course_id,))
        if not ret:
            return []
        res = [(int(perm[1]), int(perm[2])) for perm in ret if
               perm[2] in [2, 3, 4, 5, 10, 14, 11, 17, 16, 8, 9, 15]]
        # TODO: Magic numbers! get rid of them!
        return res