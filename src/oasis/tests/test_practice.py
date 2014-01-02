# Test practice related functions

# TODO:  create a fixture with a sample set of users/courses/etc so we don't
# have to keep creating them for each test

from unittest import TestCase
import os
import datetime

from oasis import app, db

from oasis.models.User import User
from oasis.models.Course import Course
from oasis.models.Topic import Topic
from oasis.models.QTemplate import QTemplate
from oasis.models.Question import Question


class TestPractice(TestCase):

    def setUp(self):

        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join('/tmp',
                                                                            'test.db')
        app.config['TESTING'] = True
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):

        db.drop_all()
        db.session.remove()

    def test_question_generate(self):
        """ Check question generation logic
        """

        user1 = User.create(
            uname="bob1",
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

        user2 = User.create(
            uname="bob2",
            passwd='',
            givenname="Bob",
            familyname="Bobsson",
            acctstatus=2,
            student_id="123456",
            email="bob2@example.com",
            expiry=None,
            source='feed',
            confirmation_code='',
            confirmed=True)

        course1 = Course.create("practicecourse", "Testing Practice 1", 0, 1)
        course2 = Course.create("practicecourse2", "Testing Practice 2", 0, 1)

        db.session.add(user1)
        db.session.add(user2)
        db.session.add(course1)
        db.session.add(course2)
        db.session.commit()

        # TODO: Actually test

