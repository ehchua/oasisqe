# -*- coding: utf-8 -*-
#
# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

import logging
from logging import log, INFO, ERROR
import hashlib, bcrypt
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


    # --- Static Methods ---

    @staticmethod
    def get(user_id):
        """ Return the user object for the give ID, or None
        """
        return User.query.filter_by(id=user_id).first()

    @staticmethod
    def verify_password(uname, clearpass):
        """ Confirm the password is correct for the given user name.
            We first try bcrypt, if it fails we try md5 to see if they have
            an old password, and if so, upgrade the stored password to bcrypt.
        """
        u = User.get_by_uname(uname)

        if not u:
            return False

        if len(u.passwd) > 40:  # it's not MD5
            hashed = bcrypt.hashpw(clearpass, u.passwd)
            if u.passwd == hashed:
                # All good, they matched with bcrypt
                return u

        # Might be an old account, check md5
        hashgen = hashlib.md5()
        hashgen.update(clearpass)
        md5hashed = hashgen.hexdigest()
        if u.passwd == md5hashed:
            # Ok, now we need to upgrade them to something more secure
            u.set_password(clearpass)
            log(INFO, "Upgrading MD5 password to bcrypt for %s" % u.uname)
            return u
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

