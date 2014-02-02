# Test assessment related functions


from unittest import TestCase
import datetime

from oasis.models import User, Course, Exam, QTemplate, UserExam
from oasis.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


class TestAssessment(TestCase):

    def setUp(self):

        self.engine = create_engine('sqlite:///:memory:')
        self.session = scoped_session(sessionmaker(autocommit=False,
                                                   autoflush=False,
                                                   bind=self.engine))
        Base.query = self.session.query_property()
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self):

        self.session.remove()

    def test_UserExam(self):
        """ Check student/exam functionality
        """

        u = User.create(
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

        date1 = datetime.datetime(2001, 10, 28, 7, 30, 0)
        date2 = datetime.datetime(2001, 10, 28, 15, 0, 0)
        date3 = datetime.datetime(2002, 1, 2, 9, 0, 0)

        course1 = Course.create("examcourse", "Testing Exams 1", 0, 1)

        exam1 = Exam.create(course1, 1, "Test 1", 1, 30, date1, date2, "123", code=None, instant=1)
        exam2 = Exam.create(course1, 1, "Test 2", 1, 30, date1, date3, "1234", code=None, instant=1)

        self.session.add(u)
        self.session.add(exam1)
        self.session.add(exam2)
        self.session.add(course1)
        self.session.commit()

        ue1 = exam1.by_student(u.id)
        ue2 = exam2.by_student(u.id)
        ue3 = exam1.by_student(u.id)

        self.assertEqual(ue1.exam, exam1.id)
        self.assertEqual(ue2.student, u.id)
        self.assertEqual(ue1.id, ue3.id)
        self.assertNotEqual(ue2.id, ue3.id)

