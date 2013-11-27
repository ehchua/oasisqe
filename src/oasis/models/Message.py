# -*- coding: utf-8 -*-
#
# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

from logging import log, INFO, WARN
from sqlalchemy import Column, Integer, String, DateTime
from oasis import db


class Message(db.Model):
    __tablename__ = 'messages'

# CREATE TABLE messages (
#    "name" character varying(200) UNIQUE PRIMARY KEY,
#    "object" integer DEFAULT 0,
#    "type" integer DEFAULT 0,
#    "updated" timestamp without time zone,
#    "by" integer DEFAULT 0,
#    "message" text
# );

    name = Column(String(200), primary_key=True)
    object = Column(Integer, default=0)
    type = Column(Integer, default=0)
    updated = Column(DateTime)
    by = Column(Integer)
    message = Column(String)

    @staticmethod
    def get_by_name(name):
        return Message.query.filter_by(name=name).first()

    @staticmethod
    def text_by_name(name):
        msg = Message.get_by_name(name)
        if not msg:
            return ""
        return msg.message

