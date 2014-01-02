# Test the model system


from unittest import TestCase
import os
import datetime


from oasis.models.User import User
from oasis.models.Feed import Feed
from oasis.models.Course import Course
from oasis.models.Group import Group
from oasis.models.Message import Message
from oasis.models.Period import Period
from oasis.models.Topic import Topic
from oasis.models.UFeed import UFeed
from oasis.models.Exam import Exam
from oasis.models.Permission import Permission
from oasis.models.QTemplate import QTemplate


from oasis import app, db


class TestApp(TestCase):

    def setUp(self):

        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join('/tmp', 'test.db')
        app.config['TESTING'] = True
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):

        db.drop_all()
        db.session.remove()

    def test_user_obj(self):

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

        self.assertEquals("bob1", u.uname)
        self.assertEquals("Bob Bobsson", u.fullname)
        self.assertTrue(u.confirmed)
        self.assertFalse(u.expiry)

        u.set_password("12345")
        self.assertTrue(u.verify_password("12345"))
        self.assertFalse(u.verify_password("123456"))
        self.assertFalse(u.verify_password(""))
        self.assertFalse(u.verify_password("1234567890"*100))
        self.assertFalse(u.verify_password("' or 1=1;"))

        u.set_password("1234")

        self.assertTrue(u.verify_password("1234"))
        self.assertFalse(u.verify_password("123456"))
        self.assertFalse(u.verify_password(""))
        self.assertFalse(u.verify_password("1234567890"*1024))
        self.assertFalse(u.verify_password("' or 1=1;"))

        passwd = u.gen_confirm_code()
        u.set_password(passwd)

        self.assertGreater(len(passwd), 5)
        self.assertTrue(u.verify_password(passwd))
        self.assertFalse(u.verify_password(""))

        u.set_password("Ab%^/")

        db.session.add(u)
        db.session.commit()

        u2 = User.get_by_uname("bob1")

        self.assertTrue(u2.verify_password("Ab%^/"))

    def test_create_course(self):

        c = Course.create("test1", "This is a test Course", 0, 4)

        self.assertEqual("test1", c.name)
        self.assertEqual(4, c.type)
        self.assertEqual(0, c.owner)
        self.assertEqual("This is a test Course", c.title)

    def test_user_permissions(self):

        u = User.create(
            uname="bob2",
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

        Permission.add_perm(u.id, 0, 1)  # superuser

        self.assertTrue(Permission.check_perm(u.id, 0, 0))

    def test_course_find(self):

        c1 = Course.create("ctest1", "Course 2", 0, 1)
        c1.active = True
        c2 = Course.create("ctest2", "Course 2", 0, 1)
        c2.active = False
        c3 = Course.create("ctest3", "Course 2", 0, 1)
        c3.active = True
        c4 = Course.create("ctest4", "Course 2", 0, 1)
        c4.active = False

        db.session.add(c1)
        db.session.add(c2)
        db.session.add(c3)
        db.session.add(c4)

        db.session.commit()

        match = list(Course.all(only_active=False))
        self.assertEqual(len(match), 4)
        self.assertListEqual(match, [c1, c2, c3, c4])

        active = list(Course.all(only_active=True))
        self.assertEqual(len(active), 2)
        self.assertListEqual(active, [c1, c3])

    def test_exam_create(self):

        date1 = datetime.datetime(2001, 10, 28, 7, 30, 0)
        date2 = datetime.datetime(2001, 10, 28, 15, 0, 0)
        date3 = datetime.datetime(2002, 1, 2, 9, 0, 0)

        course1 = Course.create("examcourse", "Testing Exams 1", 0, 1)
        course2 = Course.create("examcourse2", "Testing Exams 2", 0, 1)
        exam1 = Exam.create(course1, 1, "Test 1", 1, 30, date1, date2, "123", code=None, instant=1)
        exam2 = Exam.create(course1, 1, "Test 2", 1, 30, date1, date3, "1234", code=None, instant=1)
        exam3 = Exam.create(course2, 1, "Test 3", 1, 60, date2, date3, "", code="abcd", instant=0)

        db.session.add(exam1)
        db.session.add(exam2)
        db.session.add(exam3)
        db.session.add(course1)
        db.session.add(course2)
        db.session.commit()

        self.assertEqual(exam1.duration, 30)
        self.assertEqual(exam2.duration, 30)
        self.assertEqual(exam3.duration, 60)

        e1 = list(Exam.by_course(course1, prev_years=True))
        e2 = list(Exam.by_course(course2, prev_years=True))

        self.assertNotEqual(e1, [])
        self.assertNotEqual(e2, [])

        self.assertIn(exam1, e1)
        self.assertIn(exam2, e1)
        self.assertIn(exam3, e2)
        self.assertNotIn(exam1, e2)
        self.assertNotIn(exam2, e2)
        self.assertNotIn(exam3, e1)

    def test_topic_course(self):

        course1 = Course.create("topiccourse", "Testing Topics 1", 0, 1)
        course2 = Course.create("topiccourse2", "Testing Topics 2", 0, 1)
        db.session.add(course1)
        db.session.add(course2)
        db.session.commit()

        topic1 = Topic.create(course1.id, "Topic 1", 1, position=3)
        topic2 = Topic.create(course1.id, "Topic 2", 1, position=4)
        topic3 = Topic.create(course2.id, "Topic 3", 1, position=5)

        db.session.add(topic1)
        db.session.add(topic2)
        db.session.add(topic3)
        db.session.commit()

        self.assertTrue(topic1.id)
        self.assertTrue(topic2.id)
        self.assertTrue(topic3.id)

        self.assertEqual(topic1.course, course1.id)
        self.assertEqual(topic2.course, course1.id)
        self.assertEqual(topic3.course, course2.id)

        tc1 = list(Topic.by_course(course1.id))
        tc2 = list(Topic.by_course(course2.id))

        self.assertListEqual(tc1, [topic1, topic2])
        self.assertListEqual(tc2, [topic3, ])

    def test_qtemplate_create(self):

        u = User.create(uname="test01",
                        passwd="",
                        email="testemail1",
                        acctstatus=0,
                        givenname="Test",
                        familyname="Account",
                        source="",
                        student_id='0000004',
                        expiry=None,
                        confirmation_code="",
                        confirmed=False
        )
        db.session.add(u)
        db.session.commit()

        self.assertTrue(u)

        qt = QTemplate.create(owner=u.id,
                              title="testqtemplate1",
                              desc="Just a test",
                              marker=0,
                              scoremax=0,
                              status=0
        )

        qt.embed_id = "93456"
        db.session.add(qt)
        db.session.commit()

        self.assertEqual(qt.owner, u.id)
        self.assertEqual(qt.title, "testqtemplate1")

        qt2 = QTemplate.get_by_embedid("93456")

        self.assertEqual(qt2.owner, u.id)
        self.assertEqual(qt2.id, qt.id)
