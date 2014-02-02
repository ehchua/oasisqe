# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Miscellaneous UI functions.

"""

import os
import StringIO
import datetime

from flask import render_template, session, \
    request, redirect, abort, url_for, flash, \
    send_file, Response, render_template_string
from logging import log, INFO, ERROR

from .lib import DB, Attach, QEditor, OaConfig


MYPATH = os.path.dirname(__file__)

from oasis import app
from .lib.Audit import audit
from .models.Permission import Permission
from .lib.Util import authenticated, send_email
from .models.User import User
from .models.Message import Message
from .models.Topic import Topic
from .models.Course import Course


@app.route("/")
def index():
    """ Main landing page. Welcome them and give them some login instructions.
    """
    if 'user_id' in session:
        return redirect(url_for("main_top"))

    if OaConfig.default == "landing":
        mesg_login = Message.text_by_name("loginmotd")
        alt_landing = os.path.join(OaConfig.theme_path, "landing_page.html")
        if os.path.isfile(alt_landing):
            tmpf = open(alt_landing)
            tmpl = tmpf.read()
            tmpf.close()
            return render_template_string(tmpl, mesg_login=mesg_login)
        return render_template("landing_page.html", mesg_login=mesg_login)
    if OaConfig.default == "locallogin":
        return redirect(url_for("login_local"))
    if OaConfig.default == "webauth":
        return redirect(url_for("login_webauth_submit"))
    return render_template("landing_page.html")


@app.route("/login/local/")
def login_local():
    """ Present a login page for people with local OASIS accounts to log in"""

    mesg_login = Message.text_by_name("loginmotd")
    return render_template("login_screen_local.html", mesg_login=mesg_login)


@app.route("/login/local/submit", methods=['POST', ])
def login_local_submit():
    """ They've entered some credentials on the local login screen.
        Check them, then set up the session or redirect back with an error.
    """
    if not 'username' in request.form or not 'password' in request.form:
        log(INFO, "Failed Login")
        flash("Incorrect name or password.")
        return redirect(url_for("login_local"))

    username = request.form['username']
    password = request.form['password']

    u = User.get_by_uname(username)
    if not u or not u.verify_password(password):
        log(INFO, "Failed Login for %s" % username)
        flash("Incorrect name or password.")
        return redirect(url_for("login_local"))

    if not u.confirmed:
        flash("""Your account is not yet confirmed. You should have received
                 an email with instructions in it to do so.""")
        return redirect(url_for("login_local"))
    session['username'] = u.uname
    session['user_id'] = u.id
    session['user_givenname'] = u.givenname
    session['user_familyname'] = u.familyname
    session['user_fullname'] = u.fullname
    session['user_authtype'] = "local"

    audit(1, u.id, u.id, "UserAuth",
          "%s successfully logged in locally" % (session['username'],))

    db.session.commit()
    if 'redirect' in session:
        log(INFO, "Following redirect for %s" % username)
        target = OaConfig.parentURL + session['redirect']
        del session['redirect']
        return redirect(target)
    log(INFO, "Successful Login for %s" % username)
    return redirect(url_for("main_top"))


@app.route("/login/signup")
def login_signup():
    """ Present a signup page for people to register a new account."""
    if not OaConfig.open_registration:
        abort(404)

    return render_template("login_signup.html")


@app.route("/login/forgot_pass")
def login_forgot_pass():
    """ Ask them for their username to begin forgotten password process."""

    return render_template("login_forgot_pass.html")


@app.route("/login/forgot_pass/submit", methods=["POST", ])
def login_forgot_pass_submit():
    """ Forgot their password. Grab their username and send them a reset email.
    """

    if "cancel" in request.form:
        flash("Password reset cancelled.")
        return redirect(url_for("login_local"))

    username = request.form.get('username', None)

    if username == "admin":
        flash("""The admin account cannot do an email password reset,
                 please see the Installation instructions.""")
        return redirect(url_for("login_forgot_pass"))

    u = User.get_by_uname(username)
    if not u:
        flash("Unknown username ")
        return redirect(url_for("login_forgot_pass"))

    if not u.source == "local":
        flash("Your password is not managed by OASIS, "
              "please contact IT Support.")
        return redirect(url_for("login_forgot_pass"))

    code = u.gen_confirm_code()

    if not u.email:
        flash("We do not appear to have an email address on file for "
              "that account.")
        return redirect(url_for("login_forgot_pass"))

    text_body = render_template(os.path.join("email", "forgot_pass.txt"),
                                code=code)
    html_body = render_template(os.path.join("email", "forgot_pass.html"),
                                code=code)
    send_email(u.email,
               from_addr=None,
               subject="OASIS Password Reset",
               text_body=text_body,
               html_body=html_body)

    db.session.add(u)
    db.session.commit()

    return render_template("login_forgot_pass_submit.html")


@app.route("/login/confirm/<string:code>")
def login_confirm(code):
    """ They've clicked on a confirmation link."""
    if not OaConfig.open_registration:
        abort(404)

    if len(code) > 20:
        abort(404)

    user = User.find_by_confirmation_code(code)
    if not user:
        abort(404)
    user.confirmed = True
    user.confirmation_code = ""
    db.session.add(user)
    db.session.commit()
    return render_template("login_signup_confirmed.html")


@app.route("/login/email_passreset/<string:code>")
def login_email_passreset(code):
    """ They've clicked on a password reset link.
        Log them in (might as well) and send them to the password reset page."""
    # This will also confirm their email if they haven't.
    # Doesn't seem to be any harm in doing that

    if len(code) > 20:
        abort(404)

    user = User.find_by_confirmation_code(code)
    if not user:
        abort(404)
    user.confirmed = True
    user.confirmation_code = ""
    session['username'] = user.uname
    session['user_id'] = user.id
    session['user_givenname'] = user.givenname
    session['user_familyname'] = user.familyname
    session['user_fullname'] = user.fullname
    session['user_authtype'] = "local"
    audit(1, user.id, user.id, "UserAuth",
          "%s logged in using password reset email" % (session['username'],))

    db.session.add(user)
    db.session.commit(user)
    flash("Please change your password")
    return redirect(url_for("setup_change_pass"))


@app.route("/login/signup/submit", methods=['POST', ])
def login_signup_submit():
    """ They've entered some information and want an account.
        Do some checks and send them a confirmation email if all looks good.
    """
    # TODO: How do we stop someone using this to spam someone?
    if not OaConfig.open_registration:
        abort(404)
    form = request.form
    if not ('username' in form
            and 'password' in form
            and 'confirm' in form
            and 'email' in form):
        flash("Please fill in all fields")
        return redirect(url_for("login_signup"))

    username = form['username']
    password = form['password']
    confirm = form['confirm']
    email = form['email']

    # TODO: Sanitize username
    if username == "" or password == "" or confirm == "" or email == "":
        flash("Please fill in all fields")
        return redirect(url_for("login_signup"))

    if not confirm == password:
        flash("Passwords don't match")
        return redirect(url_for("login_signup"))

    # basic checks in case they entered their street address or something
    # a fuller check is too hard or prone to failure
    if not "@" in email or not "." in email:
        flash("Email address doesn't appear to be valid")
        return redirect(url_for("login_signup"))

    existing = User.get_by_uname(username)
    if existing:
        flash("An account with that name already exists, "
              "please try another username.")
        return redirect(url_for("login_signup"))

    user = User(uname=username,
                passwd="NOLOGIN",
                email=email,
                givenname=username,
                familyname="",
                acctstatus=1,
                studentid="",
                source="local",
                confirmation_code="",
                confirmed=False)
    user.set_password(password)
    code = user.gen_confirm_code()
    db.session.add(user)
    db.session.commit()

    text = render_template(os.path.join("email", "confirmation.txt"),
                           code=code)
    html = render_template(os.path.join("email", "confirmation.html"),
                           code=code)
    send_email(email,
               from_addr=None,
               subject="OASIS Signup Confirmation",
               text_body=text,
               html_body=html)

    return render_template("login_signup_submit.html", email=email)


@app.route("/login/webauth/error")
def login_webauth_error():
    """ They've tried to use web authentication but the web server doesn't
        appear to be providing the right credentials. Display an error page.
    """

    return render_template("login_webauth_error.html")


@app.route("/login/webauth/submit")
def login_webauth_submit():
    """ The web server should have verified their credentials and
        provide it in env['REMOTE_USER']
        Check them, then set up the session or redirect back with an error.
        If we haven't seen them before, check with our user account feed(s)
        to see if we can find them.
    """
    if not 'REMOTE_USER' in request.environ:
        log(ERROR, "REMOTE_USER not provided by web server for 'webauth'.")
        return redirect(url_for("login_webauth_error"))

    username = request.environ['REMOTE_USER']

    #  TODO: this is for UofA, how do we make it more general?
    if '@' in username:
        username = username.split('@')[0]

    user = User.get_by_uname(username)
    if not user:
        user = User(username=username, givenname='', familyname='', email='',
                    acctstatus=1, student_id='', source="",
                    expiry='', confirmation_code='', confirmed=True)
        db.session.add(user)
        audit(1, user.id, user.id, "UserAuth",
              "creating local account for webauth user %s" % username)
        db.session.commit()

    session['username'] = username
    session['user_id'] = user.id
    session['user_givenname'] = user.givenname
    session['user_familyname'] = user.familyname
    session['user_fullname'] = user.fullname
    session['user_authtype'] = "httpauth"

    audit(1, user.id, user.id, "UserAuth",
          "%s successfully logged in via webauth" % username)

    if 'redirect' in session:
        target = OaConfig.parentURL + session['redirect']
        del session['redirect']
        return redirect(target)

    return redirect(url_for("main_top"))


# Does its own auth because it may be used in embedded questions
@app.route("/att/qatt/<int:qt_id>/<int:version>/<int:variation>/<fname>")
def attachment_question(qt_id, version, variation, fname):
    """ Serve the given question attachment """
    qtemplate = DB.get_qtemplate(qt_id)
    if len(qtemplate['embed_id']) < 1:  # if it's not embedded, check auth
        if 'user_id' not in session:
            session['redirect'] = request.path
            return redirect(url_for('index'))
    if Attach.is_restricted(fname):
        abort(403)
    (mtype, fname) = Attach.q_att_details(qt_id, version, variation, fname)
    if not mtype:
        abort(404)

    expiry = datetime.datetime.utcnow() + datetime.timedelta(10)
    response = send_file(fname, mtype)
    response.headers["Expires"] = expiry.strftime("%a, %d %b %Y %H:%M:%S GMT")
    return response


@app.route("/att/qtatt/<int:qt_id>/<int:version>/<int:variation>/<fname>")
# Does its own auth because it may be used in embedded questions
def attachment_qtemplate(qt_id, version, variation, fname):
    """ Serve the given question attachment """
    qtemplate = DB.get_qtemplate(qt_id)
    if len(qtemplate['embed_id']) < 1:  # if it's not embedded, check auth
        if 'user_id' not in session:
            session['redirect'] = request.path
            return redirect(url_for('index'))
    (mtype, filename) = Attach.q_att_details(qt_id, version, variation, fname)
    if Attach.is_restricted(fname):
        abort(403)
    if not mtype:
        abort(404)
    expiry = datetime.datetime.utcnow() + datetime.timedelta(10)
    response = send_file(filename, mtype)
    response.headers["Expires"] = expiry.strftime("%a, %d %b %Y %H:%M:%S GMT")
    return response


@app.route("/logout")
# doesn't need auth. sort of obviously.
def logout():
    """ Log the user out, if they're logged in. Mainly by clearing the session.
    """

    if "user_id" in session:
        user_id = session["user_id"]
        username = session["username"]
        session.pop("user_id")
        session.clear()
        audit(1, user_id, user_id, "UserAuth", "%s logged out" % username)
    return redirect(url_for('index'))


@app.errorhandler(401)
def custom_401(error):
    """ Give them a custom 401 error
    """
    return Response('Authentication declined %s' % error,
                    401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})


@app.route("/login/webauth/flush")
def logout_and_flush():
    """ Called vi AJAX so the user doesn't see the interaction.
        We first send them an access declined to force them to send credentials.
        Then we accept those (invalid) credentials, which will flush the browser
        copy. Next time they access a page their credentials will be
        invalid so they'll have to re-login.
    """
    if not "logout" in session:
        # first hit, reject them
        session['logout'] = 1
        abort(401)

    # Job done, send them to start
    session.pop("logout")
    session.clear()
    return redirect(url_for("index"))


@app.route("/main/top")
@authenticated
def main_top():
    """ Present the top menu page """
    return render_template("main.html")


@app.route("/main/news")
@authenticated
def main_news():
    """ Present the top menu page """
    return render_template(
        "news.html",
        news=Message.text_by_name("news"),
    )


@app.route("/cadmin/<int:course_id>/editquestion/<int:topic_id>/<int:qt_id>")
@authenticated
def qedit_redirect(course_id, topic_id, qt_id):
    """ Work out the appropriate question editor and redirect to it """
    etype = DB.get_qt_editor(qt_id)
    if etype == "Raw":
        return redirect(url_for("qedit_raw_edit",
                                topic_id=topic_id,
                                qt_id=qt_id))

    flash("Unknown Question Type, can't Edit")
    return redirect(url_for('cadmin_edit_topic',
                            course_id=course_id,
                            topic_id=topic_id))


@app.route("/qedit_raw/edit/<int:topic_id>/<int:qt_id>")
@authenticated
def qedit_raw_edit(topic_id, qt_id):
    """ Present a question editor so they can edit the question template.
        Main page of editor
    """
    user_id = session['user_id']

    topic = Topic.get(topic_id)
    course = Course.get(topic.course)

    if not (Permission.check_perm(user_id, course.id, "courseadmin")
            or Permission.check_perm(user_id, course.id, "courseadmin")
            or Permission.check_perm(user_id, course.id, "questionedit")
            or Permission.check_perm(user_id, course.id, "questionsource")):
        flash("You do not have question editor privilege in this course")
        return redirect(url_for("cadmin_edit_topic",
                                course_id=course.id, topic_id=topic_id))

    course = Course.get(course.id)
    topic = Topic.get(topic_id)
    qtemplate = DB.get_qtemplate(qt_id)
    try:
        html = DB.get_qt_att(qt_id, "qtemplate.html")
    except KeyError:
        try:
            html = DB.get_qt_att(qt_id, "__qtemplate.html")
        except KeyError:
            html = "[question html goes here]"

    qtemplate['html'] = html
    attachnames = DB.get_qt_atts(qt_id, version=qtemplate['version'])
    attachments = [
        {
            'name': name,
            'mimetype': DB.get_qt_att_mimetype(qt_id, name)
        } for name in attachnames
        if not name in ['qtemplate.html', 'image.gif', 'datfile.txt',
                        '__datfile.txt', '__qtemplate.html']
    ]
    return render_template(
        "courseadmin_raw_edit.html",
        course=course,
        topic=topic,
        html=html,
        attachments=attachments,
        qtemplate=qtemplate
    )


@app.route("/qedit_raw/save/<int:topic_id>/<int:qt_id>", methods=['POST', ])
@authenticated
def qedit_raw_save(topic_id, qt_id):
    """ Accept the question editor form and save the results. """
    valid = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    user_id = session['user_id']
    topic = Topic.get(topic_id)
    course = Course.get(topic.course)
    if not (Permission.check_perm(user_id, course.id, "courseadmin")
            or Permission.check_perm(user_id, course.id, "courseadmin")
            or Permission.check_perm(user_id, course.id, "questionedit")
            or Permission.check_perm(user_id, course.id, "questionsource")):
        flash("You do not have question editor privilege in this course")
        return redirect(url_for("cadmin_edit_topic",
                                course_id=course.id,
                                topic_id=topic_id))

    form = request.form

    if 'cancel' in form:
        flash("Question editing cancelled, changes not saved.")
        return redirect(url_for("cadmin_edit_topic",
                                course_id=course.id,
                                topic_id=topic_id))

    version = DB.incr_qt_version(qt_id)
    owner = User.get(user_id)
    DB.update_qt_owner(qt_id, user_id)
    audit(3, user_id, qt_id, "qeditor",
          "version=%s,message=%s" %
          (version, "Edited: ownership set to %s" % owner.uname))

    if 'qtitle' in form:
        qtitle = form['qtitle']
        qtitle = qtitle.replace("'", "&#039;")
        title = qtitle.replace("%", "&#037;")
        DB.update_qt_title(qt_id, title)

    if 'embed_id' in form:
        embed_id = form['embed_id']
        embed_id = ''.join([ch for ch in embed_id
                            if ch in valid])
        if not DB.update_qt_embedid(qt_id, embed_id):
            flash("Error updating EmbedID, "
                  "possibly the value is already used elsewhere.")

    # They entered something into the html field and didn't upload a
    # qtemplate.html
    if not ('newattachmentname' in form
            and form['newattachmentname'] == "qtemplate.html"):
        if 'newhtml' in form:
            html = form['newhtml'].encode("utf8")
            DB.create_qt_att(qt_id,
                             "qtemplate.html",
                             "text/plain",
                             html,
                             version)

    # They uploaded a new qtemplate.html
    if 'newindex' in request.files:
        data = request.files['newindex'].read()
        if len(data) > 1:
            html = data
            DB.create_qt_att(qt_id,
                             "qtemplate.html",
                             "text/plain",
                             html,
                             version)

    # They uploaded a new datfile
    if 'newdatfile' in request.files:
        data = request.files['newdatfile'].read()
        if len(data) > 1:
            DB.create_qt_att(qt_id,
                             "datfile.txt",
                             "text/plain",
                             data,
                             version)
            qvars = QEditor.parseDatfile(data)
            for row in range(0, len(qvars)):
                DB.add_qt_variation(qt_id, row + 1, qvars[row], version)

                # They uploaded a new image file
    if 'newimgfile' in request.files:
        data = request.files['newimgfile'].read()
        if len(data) > 1:
            df = data
            DB.create_qt_att(qt_id, "image.gif", "image/gif", df, version)

    if 'newmodule' in form:
        try:
            newmodule = int(form['newmodule'])
        except (ValueError, TypeError):
            flash(form['newmodule'])
        else:
            DB.update_qt_marker(qt_id, newmodule)

    if 'newmaxscore' in form:
        try:
            newmaxscore = float(form['newmaxscore'])
        except (ValueError, TypeError):
            newmaxscore = None
        DB.update_qt_maxscore(qt_id, newmaxscore)

    newname = False
    if 'newattachmentname' in form:
        if len(form['newattachmentname']) > 1:
            newname = form['newattachmentname']
    if 'newattachment' in request.files:
        fptr = request.files['newattachment']
        if not newname:  # If they haven't supplied a filename we use
                         # the name of the file they uploaded.
            # TODO: Security check? We don't create disk files with this name
            newname = fptr.filename
        data = fptr.read()
        mtype = fptr.content_type
        DB.create_qt_att(qt_id, newname, mtype, data, version)
        log(INFO, "File '%s' uploaded by %s" % (newname, session['username']))

    flash("Question changes saved")
    return redirect(url_for("qedit_raw_edit", topic_id=topic_id, qt_id=qt_id))


@app.route("/qedit_raw/att/<int:qt_id>/<fname>")
@authenticated
def qedit_raw_attach(qt_id, fname):
    """ Serve the given question template attachment
        straight from DB so it's fresh
    """
    mtype = DB.get_qt_att_mimetype(qt_id, fname)
    data = DB.get_qt_att(qt_id, fname)
    if not data:
        abort(404)
    if not mtype:
        mtype = "text/plain"
    if mtype == "text/html":
        mtype = "text/plain"
    sIO = StringIO.StringIO(data)
    return send_file(sIO, mtype, as_attachment=True, attachment_filename=fname)
