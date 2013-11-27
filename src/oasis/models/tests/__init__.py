# Test the model system


from unittest import TestCase
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
import os
from oasis.lib import Permissions
from oasis.lib import OaConfig as config

from oasis.models.User import User
from oasis.models.Feed import Feed
from oasis.models.Course import Course
from oasis.models.Group import Group
from oasis.models.Message import Message
from oasis.models.Period import Period
from oasis.models.Topic import Topic
from oasis.models.UFeed import UFeed


app = Flask("testing",
                template_folder=os.path.join(config.homedir, "templates"),
                static_folder=os.path.join(config.homedir, "static"),
                static_url_path=os.path.join(os.path.sep, config.staticpath, "static"))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
db = SQLAlchemy(app)


class TestApp(TestCase):

    def setUp(self):

        db.create_all()

    def tearDown(self):

#            db.drop_all()
        db.session.remove()

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

        u.set_password("1234")

        self.assertTrue(User.verify_password("bob1", "1234"))
        self.assertFalse(User.verify_password("bob1", "123456"))
        self.assertFalse(User.verify_password("bob1", ""))
        self.assertFalse(User.verify_password("bob1", "1234567890"*1024))
        self.assertFalse(User.verify_password("bob1", "' or 1=1;"))

        passwd = u.gen_confirm_code()
        u.set_password(passwd)

        self.assertGreater(len(passwd), 5)
        self.assertTrue(User.verify_password("bob1", passwd))
        self.assertFalse(User.verify_password("bob1", ""))

    def test_create_course(self):

        c = Course.create("test1", "This is a test Course", 0, 4)

        self.assertEqual("test1", c.name)
        self.assertEqual(4, c.type)
        self.assertEqual(0, c.owner)
        self.assertEqual("This is a test Course", c.title)

    def test_user_permissions(self):

        u = User.create(
            username="bob2",
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

        Permissions.add_perm(u.id, 0, 1)  # superuser

        self.assertTrue(Permissions.check_perm(u.id, 0, 0))