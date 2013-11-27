# Test the model system

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
import os

from oasis.lib import OaConfig as config

from oasis.models import User
from oasis.models import Feed
from oasis.models import Course
from oasis.models import Group
from oasis.models import Message
from oasis.models import Period
from oasis.models import Topic
from oasis.models import UFeed

from oasis import app, db

class TestApp(object):

        def setUp(self):

            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tmp/oasis_test.db'

            global db

            db.create_all()

        def tearDown(selfself):

            db.session.remove()

        def test_running(self):

            print repr(db)
            assert True