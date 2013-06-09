# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Provide the UI for admin related tasks, such as configuring the system,
    Adding courses, configuring feeds, etc.
"""


import os
from datetime import datetime

from flask import render_template, session, \
    request, redirect, abort, url_for, flash

from .lib import Courses, Courses2, Setup, Periods, Feeds

MYPATH = os.path.dirname(__file__)
from .lib import DB, Groups
from oasis import app, require_perm
from logging import log, INFO


@app.route("/admin/top")
@require_perm('sysadmin')
def admin_top():
    """ Present the top level admin page """
    db_version = DB.get_db_version()
    return render_template(
        "admintop.html",
        courses=Setup.get_sorted_courselist(),
        db_version=db_version
    )


@app.route("/admin/courses")
@require_perm('sysadmin')
def admin_courses():
    """ Present page to administer courses in the system """
    courses = Setup.get_sorted_courselist(with_stats=True, only_active=False)

    return render_template(
        "admin_courselist.html",
        courses=courses
    )


@app.route("/admin/enrol/top")
@require_perm('sysadmin')
def admin_enrol_top():
    """ Present menu page of enrolment related options """
    log(INFO, "Enrol top")
    return render_template(
        "admin_enrol_top.html"
    )


@app.route("/admin/feeds")
@require_perm('sysadmin')
def admin_feeds():
    """ Present menu page of enrolment related options """

    feeds = Feeds.all_list()
    return render_template(
        "admin_group_feeds.html",
        feeds=feeds
    )


@app.route("/admin/periods")
@require_perm('sysadmin')
def admin_periods():
    """ Present page to administer time periods in the system """
    periods = Periods.all_list()

    return render_template(
        "admin_periods.html",
        periods=periods
    )


@app.route("/admin/groups")
@require_perm('sysadmin')
def admin_groups():
    """ Present page to administer time periods in the system """
    groups = Groups.all_groups()

    return render_template(
        "admin_groups.html",
        groups=groups
    )


@app.route("/admin/add_group")
@require_perm('sysadmin')
def admin_add_group():
    """ Present page to add a group to the system """
    feeds = Feeds.all_list()
    periods = Periods.all_list()
    gtypes = Groups.all_gtypes()
    return render_template(
        "admin_editgroup.html",
        feeds=feeds,
        periods=periods,
        group=Groups.Group(gtype=1),
        gtypes=gtypes
    )


@app.route("/admin/edit_group/<int:g_id>")
@require_perm('sysadmin')
def admin_edit_group(g_id):
    """ Present page to add a group to the system """
    feeds = Feeds.all_list()
    periods = Periods.all_list()
    group = Groups.Group(id=g_id)
    gtypes = Groups.all_gtypes()
    return render_template(
        "admin_editgroup.html",
        feeds=feeds,
        periods=periods,
        group=group,
        gtypes=gtypes
    )


@app.route("/admin/edit_group_submit/<int:g_id>", methods=["POST", ])
@require_perm('sysadmin')
def admin_edit_group_submit(g_id):
    """ Submit edit group form """
    if "cancel" in request.form:
        flash("Edit cancelled!")
        return redirect(url_for("admin_groups"))

    name = request.form.get('name', None)
    title = request.form.get('title', None)
    gtype = request.form.get('gtype', None)

    error = False

    if g_id == 0:  # It's a new one being created
        if Groups.get_ids_by_name(name):
            error = "A Group with that name already exists!"
        else:
            group = Groups.Group(id=0)
    else:
        try:
            group = Groups.Group(id=g_id)
        except KeyError:
            group = None
            return abort(404)

    if not name:
        error = "Can't Save: Name must be supplied"

    if not error:
        try:
            group.id = g_id
            group.name = name
            group.title = title
            group.gtype = gtype

            group.save()
        except KeyError, err:  # Probably a duplicate or something
            error = "Can't Save: %s" % err

    if error:
        flash(error)
        return redirect(url_for("admin_edit_group", g_id=group.id))

    flash("Changes saved", category='success')
    return redirect(url_for("admin_groups"))



@app.route("/admin/edit_period/<int:p_id>")
@require_perm('sysadmin')
def admin_edit_period(p_id):
    """ Present page to edit a time period in the system """
    try:
        period = Periods.Period(id=p_id)
    except KeyError:
        return abort(404)
    else:
        period.start_date = period.start.strftime("%a %d %b %Y")
        period.finish_date = period.finish.strftime("%a %d %b %Y")
    return render_template(
        "admin_editperiod.html",
        period=period
    )


@app.route("/admin/edit_feed/<int:feed_id>")
@require_perm('sysadmin')
def admin_edit_feed(feed_id):
    """ Present page to edit a feed in the system """
    try:
        feed = Feeds.Feed(id=feed_id)
    except KeyError:
        return abort(404)
    scripts = ['feed_url.py', 'feed_ldap.py', 'feed_spreadsheet.py']
    return render_template(
        "admin_edit_group_feed.html",
        feed=feed,
        scripts=scripts
    )


@app.route("/admin/add_feed")
@require_perm('sysadmin')
def admin_add_feed():
    """ Present page to add a feed to the system """
    scripts = ['feed_url.py', 'feed_ldap.py', 'feed_spreadsheet.py']
    return render_template(
        "admin_edit_group_feed.html",
        feed={'id': 0},
        scripts=scripts
    )


@app.route("/admin/add_period")
@require_perm('sysadmin')
def admin_add_period():
    """ Present page to add a time period in the system """
    return render_template(
        "admin_editperiod.html",
        period={'id': 0}
    )


@app.route("/admin/edit_group_feed_submit/<int:feed_id>", methods=["POST", ])
@require_perm('sysadmin')
def admin_edit_group_feed_submit(feed_id):
    """ Submit edit feed form """
    if "cancel" in request.form:
        flash("Edit cancelled!")
        return redirect(url_for("admin_feeds"))

    name = request.form.get('name', '')
    title = request.form.get('title', '')
    script = request.form.get('script', '')
    envvar = request.form.get('envvar', '')
    comments = request.form.get('comments', '')
    freq = int(request.form.get('freq', 1))
    active = request.form.get('active', 'inactive') == 'active'

    if feed_id == 0:  # It's a new one being created
        feed = Feeds.Feed(
            id=0,
            name=name,
            title=title,
            script=script,
            envvar=envvar,
            comments=comments,
            freq=freq,
            active=active
        )
    else:
        try:
            feed = Feeds.Feed(id=feed_id)
        except KeyError:
            return abort(404)

    feed.id = feed_id
    feed.name = name
    feed.title = title
    feed.script = script
    feed.envvar = envvar
    feed.comments = comments
    feed.freq = freq
    feed.active = active

    if name == "":
        flash("Can't Save: Name must be supplied")
        return render_template(
            "admin_edit_group_feed.html",
            feed=feed
        )

    try:
        feed.save()
    except ValueError, err:  # Probably a duplicate or something
        flash("Can't Save: %s" % err)
        return render_template(
            "admin_edit_group_feed.html",
            feed=feed
        )
    flash("Changes saved", category='success')
    return redirect(url_for("admin_feeds"))


@app.route("/admin/edit_period_submit/<int:p_id>", methods=["POST", ])
@require_perm('sysadmin')
def admin_edit_period_submit(p_id):
    """ Submit edit period form """
    if "cancel" in request.form:
        flash("Edit cancelled!")
        return redirect(url_for("admin_periods"))

    try:
        start = datetime.strptime(request.form['start'], "%a %d %b %Y")
        start_date = start.strftime("%a %d %b %Y")
    except ValueError:
        start = None
        start_date = ""

    try:
        finish = datetime.strptime(request.form['finish'], "%a %d %b %Y")
        finish_date = finish.strftime("%a %d %b %Y")
    except ValueError:
        finish = None
        finish_date = ""

    name = request.form.get('name', None)
    title = request.form.get('title', None)
    code = request.form.get('code', None)

    if p_id == 0:  # It's a new one being created
        period = Periods.Period(
            id=0,
            name=name,
            title=title,
            code=code,
            start=start,
            finish=finish
        )
    else:
        try:
            period = Periods.Period(id=p_id)
        except KeyError:
            return abort(404)

    period.id = p_id
    period.start = start
    period.finish = finish
    period.name = request.form['name']
    period.title = request.form['title']
    period.code = request.form['code']
    period.start_date = start_date
    period.finish_date = finish_date

    error = False
    if not start:
        error = "Can't Save: can't understand start date."

    if not finish:
        error = "Can't Save: can't understand finish date."

    if name == "":
        error =  "Can't Save: Name must be supplied"

    if not period.editable():
        error = "That time period is not editable!"

    try:
        period.save()
    except ValueError, err:  # Probably a duplicate or something
        error = "Can't Save: %s" % err

    if error:
        flash(error)
        return render_template(
            "admin_editperiod.html",
            period=period
        )

    flash("Changes saved", category='success')
    return redirect(url_for("admin_periods"))


@app.route("/admin/course/<int:course_id>")
@require_perm('sysadmin')
def admin_course(course_id):
    """ Present page to administer settings for a given course"""

    course = Courses2.get_course(course_id)
    course['size'] = len(Courses.get_users(course_id))

    return render_template(
        "admin_course.html",
        course=course,
    )


@app.route("/admin/add_course")
@require_perm('sysadmin')
def admin_add_course():
    """ Present page to administer settings for a given course """
    course = {
        'course_name': '',
        'course_title': '',
        'active': True
    }
    return render_template(
        "admin_add_course.html",
        course=course
    )


@app.route("/admin/course/save/<int:course_id>", methods=['POST', ])
@require_perm('sysadmin')
def admin_course_save(course_id):
    """ accept saved settings """
    form = request.form
    if 'cancel_edit' in form:
        flash("Course edits cancelled")
        return redirect(url_for("admin_courses"))

    if not 'save_changes' in form:
        abort(400)

    changed = False
    course = Courses2.get_course(course_id)
    if 'course_name' in form:
        name = form['course_name']
        if not name == course['name']:
            changed = True
            Courses.set_name(course_id, name)

    if 'course_title' in form:
        title = form['course_title']
        if not title == course['title']:
            changed = True
            Courses.set_title(course_id, title)

    if 'course_active' in form:
        active = form['course_active']
        if active == '1' or active == 1:
            active = True
        else:
            active = False
        if not (active == course['active']):
            changed = True
            Courses.set_active(course_id, active)

    if changed:
        Courses2.reload_if_needed()
        flash("Course changes saved!")
        return redirect(url_for("admin_courses"))
    course = Courses2.get_course(course_id)
    course['size'] = len(Courses.get_users(course_id))
    return render_template(
        "admin_course.html",
        course=course
    )


@app.route("/admin/add_course/save", methods=['POST', ])
@require_perm('sysadmin')
def admin_add_course_save():
    """ accept saved settings for a new course"""
    user_id = session['user_id']
    form = request.form
    if 'cancel_edit' in form:
        flash("Course creation cancelled")
        return redirect(url_for("admin_courses"))

    if not 'save_changes' in form:
        abort(400)

    if not 'course_name' in form:
        flash("You must give the course a name!")
        return redirect(url_for("admin_add_course"))

    if not 'course_title' in form:
        flash("You must give the course a title!")
        return redirect(url_for("admin_add_course"))

    name = form['course_name']
    title = form['course_title']

    if len(name) < 1:
        flash("You must give the course a name!")
        return redirect(url_for("admin_add_course"))

    if len(title) < 1:
        flash("You must give the course a title!")
        return redirect(url_for("admin_add_course"))

    course_id = Courses.create(name, title, user_id, 1)
    if not course_id:
        flash("Error Adding Course!")
        return redirect(url_for("admin_add_course"))

    if 'course_active' in form:
        active = form['course_active']
        if active == '1' or active == 1:
            active = True
        else:
            active = False
        Courses.set_active(course_id, active)

    Courses2.reload_if_needed()
    flash("Course %s added!" % name)
    course = Courses2.get_course(course_id)
    course['size'] = 0
    return render_template(
        "admin_course.html",
        course=course
    )


@app.route("/admin/edit_messages")
@require_perm('sysadmin')
def admin_editmessages():
    """ Present page to administer messages in the system """

    mesg_news = DB.get_message("news")
    mesg_login = DB.get_message("loginmotd")
    return render_template(
        "admin_editmessages.html",
        mesg_news=mesg_news,
        mesg_login=mesg_login
    )


@app.route("/admin/save_messages",
           methods=["POST", ])
@require_perm('sysadmin')
def admin_savemessages():
    """ Save messages in the system """

    form = request.form
    if 'cancel' in form:
        flash("Changes Cancelled")
        return redirect(url_for("admin_top"))

    if 'mesg_news' in form:
        DB.set_message("news", form['mesg_news'])
    if 'mesg_news' in form:
        DB.set_message("loginmotd", form['mesg_login'])
    flash("Changes saved")
    return redirect(url_for("admin_top"))