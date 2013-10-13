""" User accounts
"""

from oasis.lib.DB2 import Base
import hashlib, bcrypt
from sqlalchemy import Column, Integer, String, DateTime


class User(Base):

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


  def __init__(self, uname=None, email=None):
    self.uname = uname
    self.email = email

  def __repr__(self):
    return u"<User %s (%s, %s)>" % (self.id, self.uname, self.email)

  def set_password(self, clearpass):
    """ Updates a users password. """
    hashed = bcrypt.hashpw(clearpass, bcrypt.gensalt())
    self.passwd = hashed
    return True

  @staticmethod
  def verify_password(uname, clearpass):
    """ Confirm the password is correct for the given user name.
        We first try bcrypt, if it fails we try md5 to see if they have
        an old password, and if so, upgrade the stored password to bcrypt.
    """
    u = User.query.filter_by(uname = uname).first()

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

