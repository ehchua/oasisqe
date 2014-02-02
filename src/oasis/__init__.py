# -*- coding: utf-8 -*-
#
# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Main entry point. This uses Flask to provide a WSGI app, it should be
    run from a WSGI web server such as Apache or Nginx. """

# We include the views covering logging in/out and account signup and related.

from flask import Flask, session
import datetime
import os
import logging
from logging import log, INFO, ERROR
from logging.handlers import SMTPHandler, RotatingFileHandler

from oasis.lib import OaConfig
from oasis.lib.Audit import audit


app = Flask(__name__,
            template_folder=os.path.join(OaConfig.homedir, "templates"),
            static_folder=os.path.join(OaConfig.homedir, "static"),
            static_url_path=os.path.join(os.path.sep, OaConfig.staticpath, "static"))

app.secret_key = OaConfig.secretkey
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB max file upload
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@%s:%s/%s' % \
                                        (OaConfig.dbuname, OaConfig.dbpass, OaConfig.dbhost, OaConfig.dbport, OaConfig.dbname)

# Email error messages to admins ?
if OaConfig.email_admins:
    mh = SMTPHandler(OaConfig.smtp_server,
                     OaConfig.email,
                     OaConfig.email_admins,
                     'OASIS Internal Server Error')
    mh.setLevel(logging.ERROR)
    app.logger.addHandler(mh)

app.debug = False

if not app.debug:  # Log info or higher
    try:
        fh = RotatingFileHandler(filename=OaConfig.logfile)
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s | %(pathname)s:%(lineno)d"
        ))
        app.logger.addHandler(fh)
        logging.log(logging.INFO,
                    "File logger starting up")
    except IOError, err:  # Probably a permission denied or folder not exist
        logging.log(logging.ERROR,
                    """Unable to open log file: %s""" % err)


from oasis.database import db_session

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@app.context_processor
def template_context():
    """ Useful values for templates to always have access to"""
    if 'username' in session:
        username = session['username']
    else:
        username = None

    if "user_fullname" in session:
        user_fullname = session['user_fullname']
    else:
        user_fullname = None
    today = datetime.date.today()

    if "user_authtype" in session:
        auth_type = session['user_authtype']
    else:
        auth_type = "none"
    return {'cf': {
        'static': OaConfig.staticURL + u"/static/",
        'url': OaConfig.parentURL + u"/",
        'username': username,
        'userfullname': user_fullname,
        'email': OaConfig.email,
        'today': today,
        'auth_type': auth_type,
        'contact_url': OaConfig.contact_url,
        'feed_path': OaConfig.feed_path,
        'open_registration': OaConfig.open_registration,
        'enable_local_login': OaConfig.enable_local_login,
        'enable_webauth_login': OaConfig.enable_webauth_login,
    }}


from oasis import views_practice
from oasis import views_assess
from oasis import views_cadmin
from oasis import views_admin
from oasis import views_setup
from oasis import views_api
from oasis import views_embed
from oasis import views_misc
