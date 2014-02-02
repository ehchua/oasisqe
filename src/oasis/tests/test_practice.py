# Test practice related functions

# TODO:  create a fixture with a sample set of users/courses/etc so we don't
# have to keep creating them for each test

from unittest import TestCase
import os

from oasis.models.User import User
from oasis.models.Course import Course
from oasis.models.Topic import Topic
from oasis.models.QTemplate import QTemplate

from oasis.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


class TestPractice(TestCase):

    def setUp(self):

        self.engine = create_engine('sqlite:///:memory:')
        self.session = scoped_session(sessionmaker(autocommit=False,
                                                   autoflush=False,
                                                   bind=self.engine))
        Base.query = self.session.query_property()
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self):

        self.session.remove()

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

        # TODO: Actually test
        qt1 = QTemplate.create(owner=1,
                               title="qt 1",
                               desc="test question 1",
                               marker=1,
                               scoremax=1,
                               status=1)

        qt2 = QTemplate.create(owner=1,
                               title="qt 2",
                               desc="test question 2",
                               marker=1,
                               scoremax=1,
                               status=1)

        self.session.add(user1)
        self.session.add(user2)
        self.session.add(course1)
        self.session.add(course2)
        self.session.add(qt1)
        self.session.add(qt2)

        self.session.commit()

        t1 = Topic.create(course_id=course1.id,
                          name="Test P1",
                          visibility=4,
                          position=1)

        t2 = Topic.create(course_id=course2.id,
                          name="Test P2",
                          visibility=4,
                          position=1)

        self.session.add(t1)
        self.session.add(t2)
        self.session.commit()

        self.assertListEqual(t1.qtemplate_ids(), [])
        self.assertListEqual(t2.qtemplate_ids(), [])

        qt1.add_to_topic(t1.id, 2)
        qt2.add_to_topic(t2.id, 1)
        self.assertEqual(qt2.status, 1)
        self.assertEqual(2, qt1.topic_pos(t1.id))
        self.assertEqual(1, qt2.topic_pos(t2.id))
        self.assertNotEqual(2, qt2.topic_pos(t2.id))

        self.assertListEqual(t1.qtemplate_ids(), [(2, qt1.id), ])
        self.assertListEqual(t2.qtemplate_ids(), [(1, qt2.id), ])



