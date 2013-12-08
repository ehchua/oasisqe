# Test assessment related functions


from unittest import TestCase
import os
import datetime

from oasis import app, db

from oasis.models.User import User
from oasis.models.Course import Course
from oasis.models.Group import Group
from oasis.models.Exam import Exam
from oasis.models.QTemplate import QTemplate


class TestAssessment(TestCase):

    def setUp(self):

        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join('/tmp',
                                                                            'test.db')
        app.config['TESTING'] = True
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):

        db.drop_all()
        db.session.remove()

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

        db.session.add(exam1)
        db.session.add(exam2)
        db.session.add(course1)
        db.session.commit()

        ue1 = exam1.by_student(u.id)
        ue2 = exam2.by_student(u.id)
        ue3 = exam1.by_student(u.id)

        self.assertEqual(ue1.exam, exam1.id)
        self.assertEqual(ue2.student, u.id)
        self.assertEqual(ue1, ue3)
        self.assertNotEqual(ue2, ue3)

