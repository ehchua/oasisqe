# -*- coding: utf-8 -*-
#
# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

from logging import log, INFO, WARN
import hashlib
import bcrypt
from sqlalchemy import Column, Integer, String, DateTime
from oasis import db
from oasis.lib.Util import generate_uuid_readable


class User(db.Model):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    uname = Column(String(12), unique=True)
    passwd = Column(String(250))
    givenname = Column(String(80))
    familyname = Column(String(80))
    student_id = Column(String(20))
    acctstatus = Column(Integer)
    email = Column(String(250))
    source = Column(String(250))
    expiry = Column(DateTime)
    confirmation_code = Column(String(250))
    confirmed = Column(String(250))

    def __repr__(self):
        return u"<User %s (%s, %s)>" % (self.id, self.uname, self.email)

    def set_password(self, clearpass):
        """ Updates a users password. """
        hashed = bcrypt.hashpw(clearpass, bcrypt.gensalt())
        self.passwd = hashed
        return True

    def gen_confirm_code(self):
        """ Generate a new confirmation code and remember it.
        """
        self.confirmation_code = generate_uuid_readable(9)
        return self.confirmation_code

    @property
    def fullname(self):
        """ Return the users (calculated) full name.
        """

        return u"%s %s" % (self.givenname, self.familyname)

    #TODO: SQLAlchemyify
    def get_groups(self):
        """ Return a list of groups the user is a member of.  """

        res = db.engine.execute("SELECT groupid FROM usergroups WHERE userid=%s;", self.id)
        if res:
            return [int(row[0]) for row in res.fetchall()]
        log(WARN, "Request for unknown user or user in no groups.")
        return []

    #TODO: SQLAlchemify
    def get_courses(self):
        """ Return a list of the Course IDs of the courses the user is in """

        courses = []
        for gid in self.get_groups():
            res = db.engine.execute("SELECT course FROM groupcourses WHERE groupid=%s;", gid)
            if res:
                course_id = int(res.first()[0])
                courses.append(course_id)
        return courses

    # --- Static Methods ---

    @staticmethod
    def get(user_id):
        """ Return the user object for the give ID, or None
        """
        return User.query.filter_by(id=user_id).first()

    def verify_password(self, clearpass):
        """ Confirm the password is correct.
            We first try bcrypt, if it fails we try md5 to see if they have
            an old password, and if so, upgrade the stored password to bcrypt.
        """
        if len(self.passwd) > 40:  # it's not MD5
            hashed = bcrypt.hashpw(clearpass, self.passwd)
            if self.passwd == hashed:
                # All good, they matched with bcrypt
                return True
        # Might be an old account, check md5
        hashgen = hashlib.md5()
        hashgen.update(clearpass)
        md5hashed = hashgen.hexdigest()
        if self.passwd == md5hashed:
            # Ok, now we need to upgrade them to something more secure
            self.set_password(clearpass)
            log(INFO, "Upgrading MD5 password to bcrypt for %s" % self.uname)
            return True
        return False

    @staticmethod
    def get_by_uname(uname):
        """ Find a user by their username.
        """

        return User.query.filter_by(uname=uname).first()

    @staticmethod
    def find_by_confirmation_code(code):
        """ Given an email confirmation code, return the user_id it was given to,
            otherwise False.
        """
        if len(code) < 5:  # don't bother searching if we get an empty one
            return False
        return User.query.filter_by(confirmation_code=code).first()

    #TODO: SQLAlchemify
    @staticmethod
    def find(search, limit=20):
        """ return a list of user id's that reasonably match the search term.
            Search username then student ID then surname then first name.
            Return results in that order.
        """
        res = db.engine.execute("""SELECT id FROM users
                        WHERE LOWER(uname) LIKE LOWER(%s)
                        OR LOWER(familyname) LIKE LOWER(%s)
                        OR LOWER(givenname) LIKE LOWER(%s)
                        OR student_id LIKE %s
                        OR LOWER(email) LIKE LOWER(%s) LIMIT %s;""",
                  (search, search, search, search, search, limit))

        if res:
            return [int(row[0]) for row in res.fetchall()]

        return []

    #TODO: SQLAlchemify
    @staticmethod
    def typeahead(search, limit=20):
        """ return a list of user id's that reasonably match the search term.
            Search username then student ID then surname then first name.
            Return results in that order.
        """
        res = db.engine.execute("""SELECT id
                         FROM users
                         WHERE
                             LOWER(uname) LIKE LOWER(%s)
                           OR
                             LOWER(email) LIKE LOWER(%s)
                         LIMIT %s;""",
                      (search, search, limit))
        if res:
            return [int(row[0]) for row in res.fetchall()]
        return []

    @staticmethod
    def create(uname, passwd, givenname, familyname,
               acctstatus, student_id, email,
               expiry, source, confirmation_code,
               confirmed):

        newu = User()
        newu.uname = uname
        newu.passwd = passwd
        newu.givenname = givenname
        newu.familyname = familyname
        newu.acctstatus = acctstatus
        newu.student_id = student_id
        newu.email = email
        newu.expiry = expiry
        newu.source = source
        newu.confirmation_code = confirmation_code
        newu.confirmed = confirmed
        return newu