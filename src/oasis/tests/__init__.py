
import os
from oasis import app, db


def setUp(self):

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join('/tmp', 'test.db')
    app.config['TESTING'] = True
    self.app = app.test_client()
    db.create_all()


def tearDown(self):

    db.drop_all()
    db.session.remove()
