# -*- coding: utf-8 -*-
#
# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Main entry point. This uses Flask to provide a WSGI app, it should be
    run from a WSGI web server such as Apache or Nginx. """

# We include the views covering logging in/out and account signup and related.

from flask import Flask
import os
import logging
from logging import log, INFO, ERROR
from logging.handlers import SMTPHandler, RotatingFileHandler

from oasis.lib import OaConfig
from oasis.lib.Audit import audit

from flask.ext.sqlalchemy import SQLAlchemy


def create_app(config):

    app = Flask(__name__,
                template_folder=os.path.join(config.homedir, "templates"),
                static_folder=os.path.join(config.homedir, "static"),
                static_url_path=os.path.join(os.path.sep, config.staticpath, "static"))

    app.secret_key = config.secretkey
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB max file upload

    # Email error messages to admins ?
    if config.email_admins:
        mh = SMTPHandler(config.smtp_server,
                         config.email,
                         config.email_admins,
                         'OASIS Internal Server Error')
        mh.setLevel(logging.ERROR)
        app.logger.addHandler(mh)

    app.debug = False

    if not app.debug:  # Log info or higher
        try:
            fh = RotatingFileHandler(filename=config.logfile)
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

    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@%s:%s/%s' % (config.dbuname, config.dbpass, config.dbhost, config.dbport, config.dbname)

    return app, SQLAlchemy(app)


app, db = create_app(OaConfig)


from oasis import views_practice
from oasis import views_assess
from oasis import views_cadmin
from oasis import views_admin
from oasis import views_setup
from oasis import views_api
from oasis import views_embed
from oasis import views_misc
