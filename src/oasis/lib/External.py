# -*- coding: utf-8 -*-

""" Code that links OASIS with external systems.

    Anything that wants to run an external program or connect over the network
    (except to OASIS database or memcache servers) should come through here.
"""

from oasis.lib import OaConfig, DB
from logging import log, ERROR, INFO
import os
import subprocess
import tempfile
import json
import zipfile
import shutil
from StringIO import StringIO
from ..models.User import User
from ..models.Group import Group
from ..models.Feed import Feed
from ..models.UFeed import UFeed
from oasis import db


def feeds_available_group_scripts():
    """ Return a list of file names of available group feed scripts.
    """

    feed_dir = os.path.join(OaConfig.feed_path, "group")
    files = [
        f
        for f
        in os.listdir(feed_dir)
        if os.path.isfile(os.path.join(feed_dir, f))
    ]
    return files


def feeds_available_user_scripts():
    """ Return a list of file names of available user feed scripts.
    """

    feed_dir = os.path.join(OaConfig.feed_path, "user")
    files = [
        f
        for f
        in os.listdir(feed_dir)
        if os.path.isfile(os.path.join(feed_dir, f))
    ]
    return files


def feeds_run_group_script(filename, args=None):
    """ Run the external group script with the given args (if any).
        Return resulting output as a list of strings or raise IOError
        with an error message.
        This function may block until the script has finished so should
        only be called, eg. by a scheduled task, not triggered directly
        from the UI.
    """
    if not args:
        args = []
    # make sure we're only running code from the group feeds folder.
    safe_fname = os.path.basename(filename)
    full_path = os.path.join(OaConfig.feed_path, "group", safe_fname)
    if not os.path.isfile(full_path):
        raise IOError("Invalid group script file %s" % safe_fname)

    cmd = [full_path, ] + args
    output = subprocess.check_output(cmd)
    return output


def feeds_run_user_script(filename, args=None):
    """ Run the external group script with the given args (if any).
        Return resulting output as a list of strings or raise IOError
        with an error message.
        This function may block until the script has finished so should
        only be called, eg. by a scheduled task, not triggered directly
        from the UI.
    """
    if not args:
        args = []
    # make sure we're only running code from the user feeds folder.
    safe_fname = os.path.basename(filename)
    full_path = os.path.join(OaConfig.feed_path, "user", safe_fname)
    if not os.path.isfile(full_path):
        raise IOError("Invalid user script file %s" % safe_fname)

    cmd = [full_path, ] + args
    output = subprocess.check_output(cmd)
    return output


def group_update_from_feed(group_id, refresh_users=False):
    """ Update group membership from it's feed
        Returns (added, removed, unknown) with usernames of users
    """
    group = Group.get(group_id)
    if not group.source == 'feed':
        return

    feed = Feed.get(group.feed)
    scriptrun = ' '.join([feed.script, group.feedargs])
    try:
        output = feeds_run_group_script(feed.script, args=[group.feedargs, ])
    except BaseException, err:
        log(ERROR, "Exception in group feed '%s': %s" % (scriptrun, err))
        raise

    removed = []
    added = []
    unknown = []
    old_members = group.member_unames()
    new_members = output.split()[1:]
    for uname in new_members:
        user = User.get_by_uname(uname)
        if not user:
            users_update_from_feed([uname, ])
            log(INFO, "Group feed contained unknown user account %s" % uname)
            unknown.append(uname)
            continue
        if not uname in old_members:
            group.add_member(user.id)
            added.append(uname)

    for uname in old_members:
        if not uname in new_members:
            user = User.get_by_uname(uname)
            group.remove_member(user.id)
            removed.append(uname)

    if refresh_users:
        for uname in group.member_unames():
            user = User.get_by_uname(uname)
            user_update_details_from_feed(user.id, uname)

    return added, removed, unknown


def users_update_from_feed(upids):
    """ Given a list of upids, go through and try to fetch details from
        feed, updating/creating the accounts if needed.
    """
    for upid in upids:
        user = User.get_by_uname(upid)
        if not user:  # we don't know who they are, so create them.
            for feed in UFeed.all_list():

                try:
                    out = feeds_run_user_script(feed.script, args=[upid, ])
                except BaseException, err:
                    log(ERROR,
                        "Exception in user feed '%s': %s" % (feed.script, err))
                    continue

                res = out.splitlines()
                if res[0].startswith("ERROR"):
                    log(ERROR,
                        "Error running user feed '%s': %s" % (feed.script, res))
                    continue

                line = res[1]
                studentid = ""
                try:
                    (upid, name, email, studentid) = line.split(',')

                except ValueError:
                    try:
                        (upid, name, email) = line.split(',')
                    except ValueError:
                        continue

                given = name.split(" ")[0]
                try:
                    family = " ".join(name.split(" ")[1:])
                except ValueError:
                    family = ""
                user = User.create(uname=upid,
                            passwd='',
                            givenname=given,
                            familyname=family,
                            acctstatus=2,
                            student_id=studentid,
                            email=email,
                            expiry=None,
                            source='feed',
                            confirmation_code='',
                            confirmed=True)
                db.session.add(user)
                db.session.commit()
                break
        else:
            log(ERROR,
                "Error running user feed for existing account %s" % user.uname)
    return


def user_update_details_from_feed(uid, upid):
    """ Refresh the user's details from feed. Maybe their name or ID changed.
    """
    user = User.get(uid)
    for feed in UFeed.all_list():
        try:
            out = feeds_run_user_script(feed.script, args=[upid, ])
        except BaseException, err:
            log(ERROR,
                "Exception running user feed '%s': %s" % (feed.script, err))
            continue

        res = out.splitlines()
        if res[0].startswith("ERROR"):
            log(ERROR,
                "Error running user feed '%s': %s" % (feed.script, res))
            continue

        line = res[1]
        studentid = ""
        try:
            (upid, name, email, studentid) = line.split(',')

        except ValueError:
            try:
                (upid, name, email) = line.split(',')
            except ValueError:
                continue

        given = name.split(" ")[0]
        try:
            family = " ".join(name.split(" ")[1:])
        except ValueError:
            family = ""

        user.email = email
        user.givenname = given
        user.familyname = family
        user.student_id = studentid

    db.session.add(user)
    db.session.commit()


def qts_to_zip(qt_ids, fname="oa_export", suffix="oaq"):
    """ Take a list of QTemplate IDs and return a binary string containing
        them as an .oaq file.
        (a zip file in special format)
    """

    tmpd = tempfile.mkdtemp(prefix="oa")
    qdir = os.path.join(tmpd, fname)
    os.mkdir(qdir)
    info = {
        'oasis': {
            'oa_version': "3.9.4",
            'qt_version': '0.9',
            'url': OaConfig.parentURL
        },
        'qtemplates': {}
    }

    arc = zipfile.ZipFile(os.path.join(tmpd, "%s.%s" % (fname, suffix)),
                          'w',
                          zipfile.ZIP_DEFLATED)
    for qt_id in qt_ids:
        qtemplate = DB.get_qtemplate(qt_id)
        qtdir = os.path.join(qdir, str(qt_id))
        attachments = DB.get_qt_atts(qt_id)
        attachments.append('qtemplate.html')
        attachments.append('datfile.txt')
        attachments.append('image.gif')
        os.mkdir(qtdir)
        os.mkdir(os.path.join(qtdir, "attach"))
        info["qtemplates"][qt_id] = {'qtemplate': qtemplate}
        info["qtemplates"][qt_id]["attachments"] = []

        for name in attachments:
            mtype = DB.get_qt_att_mimetype(qt_id, name)
            data = DB.get_qt_att(qt_id, name)
            info["qtemplates"][qt_id]["attachments"].append([name, mtype, len(data)])
            subdir = os.path.join(qtdir, "attach", name)
            outf = open(subdir, "wb")
            outf.write(data)
            outf.close()
            arc.write(subdir,
                      os.path.join(fname, "%s" % qt_id, "attach", name),
                      zipfile.ZIP_DEFLATED)

    infof = open(os.path.join(qdir, "info.json"), "wb")
    infof.write(json.dumps(info))
    infof.close()
    arc.write(os.path.join(qdir, "info.json"),
              os.path.join(fname, "info.json"),
              zipfile.ZIP_DEFLATED)
    arc.close()

    readback = open(os.path.join(tmpd, "%s.%s" % (fname, suffix)), "rb")
    data = readback.read()
    readback.close()
    shutil.rmtree(tmpd)
    return data


def import_qts_from_zip(topic_id, data):
    """ Open the given OAQ file and import any qtemplates found.
        Return False if it's not valid
        Return 0 if it's valid but has no qtemplates
        Return NUM of templates imported.
    """

    # TODO: How do we protect against malicious uploads?
    # At the moment they're allowed for reasonably trusted people only,
    # but they could be tricked into uploading a bad one

    # eg.    unzip to huge size
    # add digital signatures?

    sdata = StringIO(data)
    tmpd = tempfile.mkdtemp(prefix="oa")
    qdir = os.path.join(tmpd, "import")
    os.mkdir(qdir)
    with zipfile.ZipFile(sdata, "r") as zfile:
        files = zfile.namelist()
        zfile.extractall(qdir)
        for fname in files:
            pass

    return 0