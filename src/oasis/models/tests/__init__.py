# Test the model system


from unittest import TestCase
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


class TestApp(TestCase):

        def setUp(self):

            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/oasis_test.db'
            db.create_all()

        def tearDown(self):

            db.session.remove()
            db.drop_all()

        def test_create_user(self):

            u = User.create(
                username="bob1",
                passwd='',
                givenname="Bob",
                familyname="Bobsson",
                acctstatus=2,
                student_id="123456",
                email="bob@example.com",
                expiry=None,
                source='feed',
                confirmation_code='',
                confirmed=True)

            self.assertEquals("bob1", u.uname)
            self.assertEquals("Bob Bobsson", u.fullname)
            self.assertTrue(u.confirmed)
            self.assertFalse(u.expiry)

            u.set_password("12345")

            self.assertTrue(User.verify_password("bob1", "12345"))
            self.assertFalse(User.verify_password("bob1", "123456"))
            self.assertFalse(User.verify_password("bob1", ""))
            self.assertFalse(User.verify_password("bob1", "1234567890"*1024))
            self.assertFalse(User.verify_password("bob1", "' or 1=1;"))


        def test_create_course(self):

            c = Course.create("test1","This is a test Course",0, "test")