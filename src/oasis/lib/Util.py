# -*- coding: utf-8 -*-
#
# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Miscellaneous utility functions
"""

import random
from functools import wraps
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import session, redirect, url_for, request, flash
import datetime
from .Permissions import satisfy_perms
import oasis
from . import OaConfig

app = oasis.app

# Human readable symbols
def generate_uuid_readable(length=9):
    """ Create a new random uuid suitable for acting as a unique key in the db
        Use this when it's an ID a user will see as it's a bit shorter.
        Duplicates are still unlikely, but don't use this in situations where
        a duplicate might cause problems (check for them!)

        :param length: The number of characters we want in the UUID
    """
    valid = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    # 57^n possibilities - about 6 million billion options for n=9.
    # Hopefully pretty good.
    return "".join([random.choice(valid) for _ in xrange(length)])



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


def authenticated(func):
    """ Decorator to check the user is currently authenticated and
        deal with the session/redirect """
    @wraps(func)
    def call_fn(*args, **kwargs):
        """ If they're not in session, redirect them and remember where
            they were going.
        """
        if 'user_id' not in session:
            session['redirect'] = request.path
            return redirect(url_for('index'))
        return func(*args, **kwargs)

    return call_fn


def require_perm(perms, redir="setup_top"):
    """ Decorator to check the user has at least one of a given list of global
        perms.
        Will flash() a message to them and redirect if they don't.

        example:

        @app.route(...)
        @require_perm('sysadmin', url_for('index'))
        def do_stuff():

        or

        @app.route(...)
        @require_perm(['sysadmin', 'useradmin'], url_for['admin'])
        def do_stuff():
    """

    def decorator(func):
        """ Handle decorator
        """
        @wraps(func)
        def call_fn(*args, **kwargs):
            """ check auth first, can't have perms if we're not.
            """
            if 'user_id' not in session:
                session['redirect'] = request.path
                return redirect(url_for('index'))

            user_id = session['user_id']

            if isinstance(perms, str):
                permlist = (perms,)
            else:
                permlist = perms

            if satisfy_perms(user_id, 0, permlist):
                return func(*args, **kwargs)
            flash("You do not have permission to do that.")
            return redirect(url_for(redir))

        return call_fn

    return decorator


def require_course_perm(perms, redir=None):
    """ Decorator to check the user has at least one of a given list of course
        perms.
        Will flash() a message to them and redirect if they don't.

        example:

        @app.route(...)
        @require_perm('sysadmin', url_for('index'))
        def do_stuff():

        or

        @app.route(...)
        @require_perm(['sysadmin', 'useradmin'], url_for['admin'])
        def do_stuff():
    """

    def decorator(func):
        """ Handle decorator
        """
        @wraps(func)
        def call_fn(*args, **kwargs):
            """ check auth first, can't have perms if we're not.
            """
            if 'user_id' not in session:
                session['redirect'] = request.path
                return redirect(url_for('index'))

            user_id = session['user_id']

            if isinstance(perms, str):
                permlist = (perms,)
            else:
                permlist = perms

            course_id = kwargs['course_id']

            if satisfy_perms(user_id, course_id, permlist):
                return func(*args, **kwargs)
            flash("You do not have course permission to do that.")
            if redir:
                return redirect(url_for(redir))
            else:
                return redirect(url_for("cadmin_top", course_id=course_id))

        return call_fn

    return decorator


def send_email(to_addr, from_addr=None, subject="Message from OASIS",
               text_body=None, html_body=None):
    """ Send an email to the given address.
        You must provide both an html body and a text body.

        If "from_addr" is not specified, use the default from the config file.

        Will not attempt to validate the email addresses, please do so before
        calling, but will check the database for blacklisted addresses.

        Returns True if successful, and a string containing human readable error
        message of it fails, or refuses.

        :param to_addr:  string containing the email address to send to
        :param from_addr: string containing the email address the mail is from
        :param subject: string containing the text to put in the Subject line
        :param text_body: the main text of the email
        :param html_body: an HTML version of the main text, for recipients
                          that support it.
    """

    # TODO: attempt to not send email to the same address too often,
    # to prevent us being used to annoy someone.

    _blacklist = []

    if to_addr in _blacklist:
        return "Attempting to send to blacklisted address."

    if not from_addr:
        from_addr = OaConfig.email

    if not text_body and not html_body:
        return "Attempting to send empty email"

    # Create message container - the correct MIME type is multipart/alternative.
    _msg = MIMEMultipart('alternative')
    _msg['Subject'] = subject
    _msg['From'] = from_addr
    _msg['To'] = to_addr

    # Record the MIME types of both parts - text/plain and text/html.
    _part1 = MIMEText(text_body, 'plain')
    _part2 = MIMEText(html_body, 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multi-part message, in this case
    # the HTML message, is best and preferred.
    _msg.attach(_part1)
    _msg.attach(_part2)

    # Send the message via local SMTP server.
    _smtp = smtplib.SMTP(OaConfig.smtp_server)
    # sendmail function takes 3 arguments: sender's address, recipient's address
    # and message to send - here it is sent as one string.
    _smtp.sendmail(from_addr, to_addr, _msg.as_string())
    _smtp.quit()

    return True


