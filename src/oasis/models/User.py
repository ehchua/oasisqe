""" User accounts
"""

from oasis.lib.DB2 import Base
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
