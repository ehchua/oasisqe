# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" General.py
    General and miscellaneous OASIS backend stuff

    Functions needed by several of the Oasis views
"""

from PIL import Image, ImageDraw, ImageFont
import re
import random
from StringIO import StringIO
import math
import sys
import traceback
import datetime
import time
import jinja2

from oasis.lib.OaExceptions import OaMarkerError
from . import Courses, Exams
from oasis.lib import OaConfig, DB, Topics, script_funcs, OqeSmartmarkFuncs, Audit
from logging import getLogger


L = getLogger("oasisqe")


def htmlesc(text):
    """ HTML escape the text. """
    return jinja2.escape(text)


def get_topic_list(cid, numq=True):
    """ Return a list of dicts with topic information for the given course.
        [{ tid: int       Topic ID
          name: string   Name of Topic
          num:  int      Number of questions (if numq is false, then None)
          visibility:  int    Who can see the topic. 0 = Noone, 1 = Staff,
                                                     2 = Course, 3 = Student,
                                                     4 = Guest

        },]
    """     # TODO: magic numbers!
    tlist = []
    topics = Courses.get_topics(int(cid))
    for topic in topics:
        if numq:
            num = Topics.get_num_qs(topic)
        else:
            num = None
        tlist.append({'tid': topic,
                      'name': Topics.get_name(topic),
                      'num': num,
                      'visibility': Topics.get_vis(topic)})
    return tlist


def get_q_list(tid, uid=None, numdone=True):
    """ Return a list of dicts with question template information for the topic.
        [{ qtid: int      QTemplate ID
          name: string   Name of Question
          position: int  Position of Question in topic
          done:  Number of times the given user has submitted a question
                 for practice
        },]
    """
    qlist = []
    qtemplates = Topics.get_qts(int(tid))
    for qtid in qtemplates:
        if uid and numdone:
            num = DB.get_student_q_practice_num(uid, qtid)
        else:
            num = 0
        qlist.append({'qtid': qtid,
                      'name': qtemplates[qtid]['name'],
                      'position': qtemplates[qtid]['position'],
                      'done': num})
        # Sort them by position
    qlist.sort(lambda f, s: cmp(f["position"], s["position"]))
    return qlist


def get_q_att_fname(qid, name):
    """ Return (mimetype, filename) with the relevant filename.
        If it's not found in question, look in questiontemplate.
    """
    qtid = DB.get_q_parent(qid)
    variation = DB.get_q_variation(qid)
    version = DB.get_q_version(qid)
    # for the two biggies we hit the question first,
    # otherwise check the question template first
    if name == "image.gif" or name == "qtemplate.html":

        fname = DB.get_q_att_fname(qtid, name, variation, version)
        if fname:
            return DB.get_q_att_mimetype(qtid, name, variation, version), fname
        fname = DB.get_qt_att_fname(qtid, name, version)
        if fname:
            return DB.get_qt_att_mimetype(qtid, name, version), fname
    else:
        fname = DB.get_qt_att_fname(qtid, name, version)
        if fname:
            return DB.get_qt_att_mimetype(qtid, name, version), fname
        fname = DB.get_q_att_fname(qtid, name, variation, version)
        if fname:
            return DB.get_q_att_mimetype(qtid, name, variation, version), fname
    return None, None


def get_q_att(qid, name):
    """ Return (mimetype, data) with the relevant attachment.
        If it's not found in question, look in questiontemplate.
    """
    qtid = DB.get_q_parent(qid)
    variation = DB.get_q_variation(qid)
    version = DB.get_q_version(qid)
    # for the two biggies we hit the question first,
    # otherwise check the question template first
    if name == "image.gif" or name == "qtemplate.html":
        data = DB.get_q_att(qtid, name, variation, version)
        if data:
            return DB.get_q_att_mimetype(qtid, name, variation, version), data
        data = DB.get_qt_att(qtid, name, version)
        if data:
            return DB.get_qt_att_mimetype(qtid, name, version), data
    else:
        data = DB.get_qt_att(qtid, name, version)
        if data:
            return DB.get_qt_att_mimetype(qtid, name, version), data
        data = DB.get_q_att(qtid, name, variation, version)
        if data:
            return DB.get_q_att_mimetype(qtid, name, variation, version), data
    return None, None


def gen_exam_q(exam, position, student):
    """ Generate an exam question instance for the given student and exam.
        If there are multiple qtemplates listed in a given position, one will
        be chosen at random.
    """
    qtemplates = DB.get_exam_qts_in_pos(exam, position)
    if not qtemplates:
        L.warn("DB.get_exam_qts_in_pos(%s,%s) returned a non list." %
            (exam, position))
        return False
    if len(qtemplates) < 1:
        L.warn("DB.get_exam_qts_in_pos(%s,%s) returned an empty list." %
            (exam, position))
        return False
    whichqtemplate = random.randint(1, len(qtemplates))
    qtid = qtemplates[whichqtemplate - 1]   # lists count from 0
    return gen_q(qtid, student, exam, position)


def gen_q(qtid, student=0, exam=0, position=0):
    """ Given a qtemplate, will generate a question instance.
        If student and/or exam is supplied it will be assigned appropriately.
        If exam is supplied, position must also be supplied.
        Will return the ID of the created instance.
    """
    # Pick a variation randomly
    version = DB.get_qt_version(qtid)
    numvars = DB.get_qt_num_variations(qtid, version)
    if numvars > 0:
        variation = random.randint(1, numvars)
    else:
        L.warn("No question variations (qtid=%d)" % qtid)
        Audit.audit(3, student, qtid, "General", "Failed to generate question %s for %s, exam %s" % (qtid, student, exam))

        return False
    q_id = gen_q_from_var(qtid, student, exam, position, version, variation)
    if not q_id:
        Audit.audit(3, student, qtid, "General", "Failed to generate instance of %s for %s, exam %s" % (qtid, student, exam))
    return q_id


def gen_q_from_var(qt_id, student, exam, position, version, variation):
    """ Generate a question given a specific variation. """
    qvars = None
    q_id = DB.create_q(qt_id,
                       DB.get_qt_name(qt_id),
                       student,
                       1,
                       variation,
                       version,
                       exam)
    try:
        q_id = int(q_id)
        assert (q_id > 0)
    except (ValueError, TypeError, AssertionError):
        L.error("OaDB.createQuestion(%s,...) FAILED" % qt_id)
    imageexists = DB.get_q_att_mimetype(qt_id, "image.gif", variation, version)
    if not imageexists:
        if not qvars:
            qvars = DB.get_qt_variation(qt_id, variation, version)
        qvars['Oasis_qid'] = q_id
        image = DB.get_qt_att(qt_id, "image.gif", version)
        if image:
            newimage = gen_q_image(qvars, image)
            DB.create_q_att(qt_id,
                            variation,
                            "image.gif",
                            "image/gif",
                            newimage,
                            version)
    htmlexists = DB.get_q_att_mimetype(qt_id,
                                       "qtemplate.html",
                                       variation,
                                       version)
    if not htmlexists:
        if not qvars:
            qvars = DB.get_qt_variation(qt_id, variation, version)
        html = DB.get_qt_att(qt_id, "qtemplate.html", version)
        if html:
            qvars['Oasis_qid'] = q_id
            newhtml = gen_q_html(qvars, html)
            L.info("generating new qattach qtemplate.html for %s" % q_id)
            DB.create_q_att(qt_id,
                            variation,
                            "qtemplate.html",
                            "application/oasis-html",
                            newhtml,
                            version)
    try:
        q_id = int(q_id)
        assert (q_id > 0)
    except (ValueError, TypeError, AssertionError):
        L.error("generateQuestionFromVar(%s,%s), can't find qid %s? " %
                   (qt_id, student, q_id))
    if exam >= 1:
        DB.add_exam_q(student, exam, q_id, position)
    return q_id


def gen_q_html(qvars, html):
    """ Create an instance of the HTML """
    html = html.replace("<IMG SRC>", '<IMG SRC="$IMAGES$image.gif" />')
    # replace <ANSWERn size> with the correct HTML
    rx_answern = re.compile(r'<ANSWER([0-9]+) ([0-9]+)>')
    html = re.sub(rx_answern,
                  (lambda x:
                   """<INPUT class='auto_save' TYPE='text' NAME='ANS_%s' SIZE='%s' VALUE="VAL_%s"/>""" %
                   (x.group(1), x.group(2), x.group(1))), html)
    # replace <ANSWERn> with the correct HTML
    rx_answern = re.compile(r'<ANSWER([0-9]+)>')
    html = re.sub(rx_answern,
                  (lambda x:
                   """<INPUT class='auto_save' TYPE='text' NAME='ANS_%s' VALUE="VAL_%s"/>""" %
                   (x.group(1), x.group(1))), html)
    # replace <ANSWERn TEXT> with the correct HTML
    rx_answern = re.compile(r'<ANSWER([0-9]+) TEXT>')
    html = re.sub(rx_answern,
                  (lambda x:
                   """<TEXTAREA class='auto_save' NAME='ANS_%s' ROWS=6 COLS=100>VAL_%s</TEXTAREA>""" %
                   (x.group(1), x.group(1))), html)
    # Do multiple choice
    # TODO: need to replace with regex at some point
    #  '<ANSWER(.+?)\s+(.+?)\s+(.*?)>'
    for i in range(1, 49):
        (match, repl) = handle_multi_f(html, i, qvars)
        if match:
            html = html.replace(match, repl)
    for i in range(1, 49):
        (match, repl) = handle_multi(html, i, qvars)
        if match:
            html = html.replace(match, repl)
    for i in range(1, 49):
        (match, repl) = handle_multi_v(html, i, qvars)
        if match:
            html = html.replace(match, repl)
        # Do listbox
    # TODO: need to replace with regex at some point
    #  '<ANSWER(.+?)\s+(.+?)\s+(.*?)>'
    for i in range(1, 49):
        (match, repl) = handle_listbox(html, i, qvars)
        if match:
            html = html.replace(match, repl)
    for v in qvars.keys():
        html = html.replace("<VAL %s>" % (v,),
                            '%s' % (qvars[v]))
        html = html.replace("<IMG SRC %s>" % (v,),
                            '<IMG SRC="$STATIC$%s" />' % (qvars[v]))
        html = html.replace("<ATT SRC %s>" % (v,),
                            '<A HREF="$STATIC$%s" TARGET="_new">%s(View in New Window)</a>' % (qvars[v], qvars[v]))
    return html


def gen_q_image(qvars, image):
    """ Draw values onto the image provided. """
    img = Image.open(StringIO(image)).convert("RGBA")
    imgdraw = ImageDraw.Draw(img)
    font = ImageFont.truetype("%s/fonts/Courier_New.ttf" % OaConfig.homedir, 14)
    coords = [int(name[1:])
              for name in qvars.keys()
              if re.search("^X([0-9]+)$", name) > 0]
    for coord in coords:
        (xcoord, ycoord, value) = (qvars["X%d" % coord],
                                   qvars["Y%d" % coord],
                                   qvars["Z%d" % coord])
        if (xcoord > -1) and (ycoord > -1):
            value = unicode(value, "utf-8")    # convert to unicode
            try:
                imgdraw.text((int(xcoord), int(ycoord)), value, font=font, fill="black")
            except UnicodeEncodeError as err:
                L.warn(u"Unicode error generating image: %s [%s]." % (err, value))
    data = StringIO("")
    img.save(data, "GIF")
    return data.getvalue()


def handle_multi_f(html, answer, qvars):
    """ Convert MULTIF answer tags into appropriate HTML. (radio buttons)
        Keeps the original order (doesn't shuffle the options)

        Expects something like <ANSWERn MULTIF a,b,c,d,e>
    """
    try:
        start = html.index("<ANSWER%d MULTIF " % answer)
    except ValueError:
        return None, None
    try:
        end = html.index(">", start) + 1
    except ValueError:
        return None, None
    params = html[start + len("<ANSWER%d MULTIF " % answer):end - 1]
    match = html[start:end]
    paramlist = params.split(',')
    pout = ["", ]
    if paramlist:
        pout = ["", ]
        pcount = 0
        for param in paramlist:
            pcount += 1
            if param in qvars:
                pout += ["<td CLASS='multichoicecell'>"]
                pout += ["<INPUT class='auto_save' TYPE='radio' NAME='ANS_%d' VALUE='%d' Oa_CHK_%d_%d>%s</td>" % (
                    answer, pcount, answer, pcount, qvars[param])]
            else:
                pout += ["""<FONT COLOR="red">ERROR IN QUESTION DATA</FONT>"""]

    ret = "<table border=0><tr><td>Please choose one:</td>"
    ret += ''.join(pout)
    ret += "</tr></table><br />\n"
    return match, ret


def handle_multi_v(html, answer, qvars):
    """ Convert MULTIV answer tags into appropriate HTML. (radio buttons)
        Keeps the original order (doesn't shuffle the options)

        Expects something like  <ANSWERn MULTIV a,b,c,d>
    """
    try:
        start = html.index("<ANSWER%d MULTIV " % answer)
    except ValueError:
        return None, None
    try:
        end = html.index(">", start) + 1
    except ValueError:
        return None, None
    params = html[start + len("<ANSWER%d MULTIV " % answer):end - 1]
    match = html[start:end]
    paramlist = params.split(',')
    pout = ["", ]
    if paramlist:
        pout = ["", ]
        pcount = 0
        for param in paramlist:
            pcount += 1
            pt = 'abcdefghijklmnopqrstuvwxyz'[pcount - 1]
            if param in qvars:
                pout += ["<tr><th>%s)</th><td>" % pt, ]
                pout += "<INPUT class='auto_save' TYPE='radio' NAME='ANS_%d' VALUE='%d' Oa_CHK_%d_%d>" % (
                    answer, pcount, answer, pcount)
                pout += "</td><td CLASS='multichoicecell'> %s</td></tr>" % qvars[param]

            else:
                pout += ["""<tr><td>&nbsp;</td><td><FONT COLOR="red">ERROR IN QUESTION DATA</FONT></td></tr>"""]
    ret = "<table border=0><tr><th>Please choose one:</th></tr>"
    ret += ''.join(pout)
    ret += "</table><br />\n"
    return match, ret


def handle_multi(html, answer, qvars, shuffle=True):
    """ Convert MULTI answer tags into appropriate HTML. (radio buttons)
    """
    try:
        start = html.index("<ANSWER%d MULTI " % answer)
    except ValueError:
        return None, None
    try:
        end = html.index(">", start) + 1
    except ValueError:
        return None, None
    params = html[start + len("<ANSWER%d MULTI " % answer):end - 1]
    match = html[start:end]
    paramlist = params.split(',')
    pout = ["", ]
    if paramlist:
        pout = ["", ]
        pcount = 0
        for param in paramlist:
            pcount += 1
            if param in qvars:
                pout += [
                    "<td CLASS='multichoicecell'>",
                    "<INPUT class='auto_save' TYPE='radio' NAME='ANS_%d' VALUE='%d' Oa_CHK_%d_%d> %s</td>" % (
                        answer, pcount, answer, pcount, qvars[param])]
            else:
                pout += ["""<FONT COLOR="red">ERROR IN QUESTION DATA</FONT>"""]
        # randomise the order in the list at least a little bit
    if shuffle:
        random.shuffle(pout)
    ret = "<table border=0><tr><th>Please choose one:</th>"
    ret += ''.join(pout)
    ret += "</tr></table><br />\n"
    return match, ret


def handle_listbox(html, answer, qvars, shuffle=True):
    """ Convert SELECT answer tags into appropriate HTML (SELECT box)

        We expect    <ANSWERn SELECT a,b,c,d,e>
        with 2+ parameters (a,b,c,d,...)
    """
    try:
        start = html.index("<ANSWER%d SELECT " % answer)
    except ValueError:
        return None, None
    try:
        end = html.index(">", start) + 1
    except ValueError:
        return None, None
    params = html[start + len("<ANSWER%d SELECT " % answer):end - 1]
    match = html[start:end]
    paramlist = params.split(',')
    pout = ["", ]
    if paramlist:
        pout = ["", ]
        pcount = 0
        for param in paramlist:
            pcount += 1
            if param in qvars:
                pout += ["""<OPTION VALUE='%d' Oa_SEL_%d_%d>%s</OPTION>""" %
                         (pcount, answer, pcount, qvars[param])]
            else:
                pout += ["""<OPTION><FONT COLOR="red">ERROR IN QUESTION DATA</FONT></OPTION>"""]
        # this should randomise the order in the list at least a little bit
    if shuffle:
        random.shuffle(pout)
    ret = """<SELECT class='auto_save' NAME='ANS_%d'>Please choose:""" % answer
    ret += """<OPTION VALUE='None'>--Choose--</OPTION>"""
    ret += ''.join(pout)
    ret += "</SELECT>\n"
    return match, ret


def render_q_html(q_id, readonly=False):
    """ Fetch the question html and get it ready for display - replacing
        links with appropriate targets and filling in form details."""
    try:
        q_id = int(q_id)
        assert q_id > 0
    except (ValueError, TypeError, AssertionError):
        L.warn("renderQuestionHTML(%s,%s) called with bad qid?" % (q_id, readonly))
    qt_id = DB.get_q_parent(q_id)
    try:
        qt_id = int(qt_id)
        assert qt_id > 0
    except (ValueError, TypeError, AssertionError):
        L.warn("renderQuestionHTML(%s,%s), getparent failed? " % (q_id, readonly))
    variation = DB.get_q_variation(q_id)
    version = DB.get_q_version(q_id)
    data = DB.get_q_att(qt_id, "qtemplate.html", variation, version)
    if not data:
        L.warn("Unable to retrieve qtemplate for q_id: %s" % q_id)
        return "QuestionError"
    try:
        out = unicode(data, "utf-8")
    except UnicodeDecodeError:
        try:
            out = unicode(DB.get_q_att(qt_id, "qtemplate.html", variation, version),
                          "latin-1")
        except UnicodeDecodeError as err:
            L.error("unicode error decoding qtemplate for q_id %s: %s" % (q_id, err))
            raise
    out = out.replace("This question is not verified yet, please report any error!", "")

    out = out.replace("ANS_", "Q_%d_ANS_" % (q_id,))
    out = out.replace("$IMAGES$",
                      "%s/att/qatt/%s/%s/%s/" %
                      (OaConfig.parentURL, qt_id, version, variation))
    out = out.replace("$APPLET$",
                      "%s/att/qatt/%s/%s/%s/" %
                      (OaConfig.parentURL, qt_id, version, variation))
    out = out.replace("$STATIC$",
                      "%s/att/qtatt/%s/%s/%s/" %
                      (OaConfig.parentURL, qt_id, version, variation))
    if readonly:
        out = out.replace("<INPUT ", "<INPUT READONLY ")
        out = out.replace("<SELECT ", "<SELECT DISABLED=DISABLED STYLE='color: black;'")
    guesses = DB.get_q_guesses(q_id)
    for guess in guesses.keys():
        # noinspection PyComparisonWithNone
        if guesses[guess] == None:  # If it's 0 we want to leave it alone
            guesses[guess] = ""
        if guesses[guess] == "None":
            guesses[guess] = ""
            # for each question
    if guesses:
        for ques in range(25, 0, -1):
            if ("G%d" % ques) in guesses:
                out = out.replace("VAL_%d" % ques, htmlesc(guesses["G%d" % ques]))
                for part in range(50, 0, -1):
                    if guesses["G%d" % ques] == "%s.0" % part or guesses["G%d" % ques] == "%s" % part:
                        out = out.replace("Oa_SEL_%d_%d" % (ques, part),
                                          "SELECTED")
                        out = out.replace("Oa_CHK_%d_%d" % (ques, part),
                                          "CHECKED")
                    else:
                        out = out.replace("Oa_SEL_%d_%d" % (ques, part),
                                          "")
                        out = out.replace("Oa_CHK_%d_%d" % (ques, part),
                                          "")
            else:
                out = out.replace("VAL_%d" % (ques,), "")
    for ques in range(25, 0, -1):
        out = out.replace("VAL_%d" % (ques,), "")
    return out


# parseExpo interprets an input like "1.602 x 10^19" and returns
# a tuple ("1.602e19",1.602e19), i.e., a reformatted string and an
# attempt to convert it to float.
# The function is quite permissive. "+ .3 X 10^ (- 4)" would work as well.
# Specifically, it matches an optional (+ or -) sign, followed by optional
# space, followed by a number in any of these forms: 4 or 4. or 4.3 or .3
# or with the dot replaced by a comma (like in some countries: 4,3)
# (but not just "." or ","), followed by a multiplier (x,X, or *) then 10 then "^"
# with arbitrary spacing in between those bits, followed by the (integer)
# exponent, with optional sign, spacing anywhere, and even surrounded by
# optional parentheses. Anything else is ignored and the string is left unchanged.

re_expo = re.compile(
    r"^ *((?:[+-]? *[0-9]+(?:[\.,][0-9]*)?)|(?:[+-]? *[\.,][0-9]+)) *[xX\*] *10 *\^ *(?:([+-]? *[0-9]+)|\( *([+-]? *[0-9]+) *\)) *$")


def parseexpo(scifmt):
    """ Work out the exponent and mantisse of a number in  1.232e1231 syntax
    :param scifmt:
    :return:
    """
    resu = re_expo.search(scifmt)
    if not resu:
        return scifmt, None
    parts = [part for part in resu.groups() if part]
    if len(parts) != 2:
        return scifmt, None
    mantisse = parts[0].replace(" ", "").replace(",", ".")
    expo = parts[1].replace(" ", "")
    news = mantisse + "e" + expo
    try:
        f = float(news)
    except (TypeError, ValueError):
        f = None
    return news, f


def mark_q_standard(qvars, answers):
    """ Mark the question using the standard method
        if numerical answer is within tolerance% of the answer, it gets 1 mark.
    """
    if not qvars:
        L.warn("error: No qvars provided!")
        qvars = {}
    parts = [var[1:]
             for var in qvars.keys()
             if re.search("^A([0-9]+$)", var) > 0]
    marks = {}
    for part in parts:
        try:
            guess = answers["G%s" % (part,)]
        except KeyError:
            L.info("null guess %s" % part)
            guess = "None"
        # noinspection PyComparisonWithNone
        if guess == None:   # If it's 0 we want to leave it alone
            guess = "None"
        if guess == "":
            guess = "None"
        correct = qvars["A%s" % part]
        # noinspection PyComparisonWithNone
        if correct == None:  # If it's 0 we want to leave it alone
            correct = "None"
        if correct == "":
            correct = "None"
        marks["G%s" % part] = guess
        marks["A%s" % part] = correct
        try:
            tolerance = float(qvars["T%s" % part])
        except (KeyError, ValueError):
            tolerance = 0
        marks["T%s" % part] = tolerance
        try:   # See if we can convert it to numeric form
            correct = float(correct)
            if "NaN" in guess or "inf" in guess:
                guess = ""
            guess = float(guess)
            gtype = "float"
        except (KeyError, ValueError, TypeError):  # Guess not
            try:  # How about exponential?
                (st, flt) = parseexpo(guess)
                if flt:
                    guess = flt
                    gtype = "float"
                else:
                    gtype = "string"
            except (KeyError, ValueError, TypeError):  # no, treat it as string
                gtype = "string"
        if gtype == "string":   # Occasionally people use , instead of .
                                # which is ok in Europe.
            guess = guess.replace(",", ".")
            try:   # See if we can convert it to numeric form
                guess = float(guess)
                correct = float(correct)
                gtype = "float"
            except (ValueError, TypeError):  # Guess not
                pass
        if gtype == "float":
            if script_funcs.within_tolerance(guess, correct, tolerance):
                marks["M%s" % (part,)] = 1.0
                marks["C%s" % (part,)] = "Correct"
            else:
                marks["M%s" % (part,)] = 0
                marks["C%s" % (part,)] = "Incorrect"
        if gtype == "string":
            if str(guess).lower() == str(correct).lower():
                marks["M%s" % (part,)] = 1.0
                marks["C%s" % (part,)] = "Correct"
            else:
                marks["M%s" % (part,)] = 0
                marks["C%s" % (part,)] = "Incorrect"
    return marks


def mark_q_script(qvars, script, answer):
    """ Use the given script to mark the question.
    """
    marks = {}
    for name in qvars:
        try:   # See if we can convert it to numeric form
            if "NaN" in qvars[name] or "inf" in qvars[name]:
                qvars[name] = ""
            qvars[name] = float(qvars[name])
        except (KeyError, ValueError, TypeError):  # Guess not
            pass
    parts = [int(var[1:])
             for var in qvars.keys()
             if re.search("^A([0-9]+)$", var) > 0]
    # Set up the functions scripts can call
    qvars["__builtins__"] = {'MyFuncs': OqeSmartmarkFuncs,
                             'withinTolerance': script_funcs.within_tolerance,
                             'math': math,
                             'round': round,
                             'float': float,
                             'abs': abs,
                             'log': script_funcs.marker_log_fn,
                             'None': None,
                             'True': True,
                             'False': False}
    qvars['numanswers'] = len(parts)
    for part in parts:
        marks['A%d' % part] = qvars['A%d' % part]
        if 'A%d' % part in qvars:
            try:   # See if we can convert it to numeric form
                qvars['A%d' % part] = float(qvars['A%d' % part])
            except (KeyError, ValueError, TypeError):  # Guess not
                pass
        else:
            qvars['A%d' % part] = None

        if ('G%d' % part) in answer:
            guess = answer['G%d' % part]
            try:   # See if we can convert it to numeric form
                qvars['G%d' % part] = float(guess)
            except (KeyError, ValueError, TypeError):
                try:  # How about exponential?
                    (st, flt) = parseexpo(guess)
                    if flt:
                        qvars['G%d' % part] = flt
                    else:
                        # Occasionally people use , instead of .
                        # which is ok in Europe.
                        guess = guess.replace(",", ".")
                        flt = float(guess)
                        qvars['G%d' % part] = flt
                except (KeyError, ValueError, TypeError):  # treat it as string
                    qvars['G%d' % part] = answer['G%d' % part]
        else:
            qvars['G%d' % part] = "None"
        if qvars['G%d' % part] == "":
            qvars['G%d' % part] = "None"
    try:
        qid = qvars['OaQID']
    except KeyError:
        qid = -1
    try:
        exec (script, qvars)
    except BaseException:
        (etype, value, tb) = sys.exc_info()
        script_funcs.q_log(qid,
                           "error",
                           "__marker.py",
                           "Falling back to standard marker __marker.py: %s" % (
                               traceback.format_exception(etype, value, tb)[-2:]))
    try:
        qid = qvars['OaQID']
    except KeyError:
        qid = -1
    if 'C0' in qvars:
        parts.append(0)
    for part in parts:
        if not part == 0:
            marks["M%d" % part] = qvars["M%d" % part]
        comment = qvars["C%d" % part]
        for v in qvars.keys():
            comment = comment.replace("<VAL %s>" % v,
                                      '%s' % qvars[v])
            comment = comment.replace("<IMG SRC %s>" % v,
                                      '<IMG SRC="$OaQID$%s" />' % qvars[v])
            comment = comment.replace("<ATT SRC %s>" % v,
                                      '<A HREF="$OaQID$%s" TARGET="_new">(View in New Window)</a>' % qvars[v])
            # Run twice to cope with basic nesting.
        for v in qvars.keys():
            comment = comment.replace("<VAL %s>" % v, '%s' % qvars[v])
            comment = comment.replace("<IMG SRC %s>" % v, '<IMG SRC="$OaQID$%s" />' % qvars[v])
            comment = comment.replace("<ATT SRC %s>" % v,
                                      '<A HREF="$OaQID$%s" TARGET="_new">(View in New Window)</a>' % qvars[v])
        comment = comment.replace("$OaQID$", "%d/" % qid)
        marks["C%d" % part] = comment
        if not part == 0:
            marks["G%d" % part] = qvars["G%d" % part]
            marks["T%d" % part] = qvars["T%d" % part]
    return marks


def render_mark_results_standard(qid, marks):
    """Display a nice little HTML table showing the marking for the question. """
    out = u""
    parts = [int(var[1:])
             for var in marks.keys()
             if re.search("^A([0-9]+)$", var) > 0]
    parts.sort()
    out += u"<table class='results'><TR>"
    out += u"<TH>Part</th><th>Your Answer</th>"
    out += u"<th>Correct Answer</th><th>Tolerance</th>"
    out += u"<th>Marks</th><th>Comment</th></tr>"
    total = 0.0
    for part in parts:
        if marks['C%d' % (part,)] == 'Correct':
            marks['C%d' % (part,)] = "<b><font color='darkgreen'>Correct</font></b>"
        out += u"<TR><TD>%d</TD><TD>%s</TD><TD>%s</TD><TD>%g%%</TD><TD>%.1f</TD><TD>%s</TD></TR>" % (
            part, htmlesc(marks['G%d' % part]), marks['A%d' % part], marks['T%d' % part],
            marks['M%d' % (part,)], marks['C%d' % (part,)])
        if ('M%d' % part) in marks:
            total += float(marks['M%d' % (part,)])
    out += u"<tr><th>&nbsp;</th><th>&nbsp;</th><th>&nbsp;</th><th>&nbsp;</th><TH>Total:</th><td>%s</td></tr>" % total
    if 'C0' in marks:
        out += u"<tr><td colspan='6'>&nbsp;</td></tr>"
        out += u"<tr><th>&nbsp;</th><th valign='top'>Overall Comment:</th><td colspan='4'>%s</td></tr>" % (
            marks['C0'],)
    out += u"</table>\n<hr />"
    out += render_q_html(qid, readonly=True)
    return out


def render_mark_results_script(qtid, qid, marks, script):
    """Run the provided script to show the marking for the
       question.
    """
    version = DB.get_q_version(qid)
    variation = DB.get_q_variation(qid)
    qvars = DB.get_qt_variation(qtid, variation, version)
    questionhtml = render_q_html(qid, readonly=True)
    reshtml = ""
    qvars["__builtins__"] = {'MyFuncs': OqeSmartmarkFuncs,
                             'withinTolerance': script_funcs.within_tolerance,
                             'math': math,
                             'round': round,
                             'float': float,
                             'log': script_funcs.result_log_fn(qid),
                             'dir': dir,
                             'abs': abs,
                             'None': None,
                             'True': True,
                             'False': False,
                             'questionHTML': questionhtml,
                             'int': int,
                             'resultsHTML': reshtml}
    qvars['markeroutput'] = marks
    guesses = [int(var[1:])
               for var in marks.keys()
               if re.search(r"^G([0-9]+)$", var) > 0]
    answers = [int(var[1:])
               for var in marks.keys()
               if re.search(r"^A([0-9]+)$", var) > 0]
    tolerances = [int(var[1:])
                  for var in marks.keys()
                  if re.search(r"^T([0-9]+)$", var) > 0]
    scores = [int(var[1:])
              for var in marks.keys()
              if re.search(r"^M([0-9]+)$", var) > 0]
    comments = [int(var[1:])
                for var in marks.keys()
                if re.search(r"^C([0-9]+)$", var) > 0]
    qvars['guesses'] = {}
    qvars['answers'] = {}
    qvars['tolerances'] = {}
    qvars['scores'] = {}
    qvars['comments'] = {}
    for guess in guesses:
        qvars['guesses'][guess] = marks['G%d' % guess]
    for answer in answers:
        qvars['answers'][answer] = marks['A%d' % answer]
    for tolerance in tolerances:
        qvars['tolerances'][tolerance] = marks['T%d' % tolerance]
    for score in scores:
        qvars['scores'][score] = marks['M%d' % score]
    for comment in comments:
        qvars['comments'][comment] = marks['C%d' % comment]
    qvars['numparts'] = len(answers)
    qvars['parts'] = range(1, len(answers) + 1)
    try:
        exec (script, qvars)
    except BaseException:
        (etype, value, tb) = sys.exc_info()
        script_funcs.q_log(qid,
                           "error",
                           "__results.py",
                           "Reverting to standard display: __results.py: %s" % (
                           traceback.format_exception(etype, value, tb)[-2:]))
    if 'resultsHTML' in qvars:
        if len(qvars['resultsHTML']) > 2:
            reshtml = qvars['resultsHTML']
            for v in qvars.keys():
                reshtml = reshtml.replace("<IMG SRC %s>" % v,
                                        '<IMG SRC="$OaQID$%s" />' % qvars[v])
            reshtml = reshtml.replace("$OaQID$", "%d/" % qid)
            return reshtml
    script_funcs.q_log(qid,
                       "error",
                       "__results.py",
                       "'resultsHTML' not set, using standard renderer.")
    return render_mark_results_standard(qid, marks)


def render_mark_results(qid, marks):
    """Take the marking results and display something for the student
       that tells them what they got right and wrong.
       If the question has an attachment "_rendermarks.py", it will be called,
       otherwise a default HTML table will be returned. _rendermarks.py should
       set variable "resultsHTML" to contain a suitable string for putting
       in an HTML page.
    """
    qtid = DB.get_q_parent(qid)
    renderscript = DB.get_qt_att(qtid, "__results.py")
    if not renderscript:
        resultshtml = render_mark_results_standard(qid, marks)
    else:
        resultshtml = render_mark_results_script(qtid, qid, marks, renderscript)
    return resultshtml


def mark_q(qid, answers):
    """ Mark the question according to the answers given in a dictionary and
        return the result in a dictionary:
        input:    {"A1":"0.345", "A2":"fred", "A3":"-26" }
        return:   {"M1": Mark One, "C1": Comment One, "M2": Mark Two..... }
    """
    qtid = DB.get_q_parent(qid)
    version = DB.get_q_version(qid)
    variation = DB.get_q_variation(qid)
    qvars = DB.get_qt_variation(qtid, variation, version)
    if not qvars:
        qvars = {}
        L.warn("markQuestion(%s, %s) unable to retrieve variables." % (qid, answers))
    qvars['OaQID'] = int(qid)
    marktype = DB.get_qt_marker(qtid)
    if marktype == 1:    # standard
        marks = mark_q_standard(qvars, answers)
    else:
        # We want the latest version of the marker, so no version given
        markerscript = DB.get_qt_att(qtid, "__marker.py")
        if not markerscript:
            markerscript = DB.get_qt_att(qtid, "marker.py")
            L.info("'marker.py' should now be called '__marker.py' (qtid=%s)" % qtid)
        if not markerscript:
            L.info("Unable to retrieve marker script for smart marker question (qtid=%s)!" % qtid)
            marks = mark_q_standard(qvars, answers)
        else:
            marks = mark_q_script(qvars, markerscript, answers)
    return marks


def is_now(start, end):
    """ Return True if now is in the given period"""
    return is_between(datetime.datetime.now(), start, end)


def is_between(date, start, end):
    """ Return True if the given date is between the start and end date.
        All arguments should be datetime objects.
    """
    if start < end:
        return end > date > start

    return start > date > end


def is_recent(date):
    """ Return True if the given date (datetime object) is in the near past.
        Currently this means within 24 hours, but that may change.
    """
    end = datetime.datetime.now()
    start = end - datetime.timedelta(1)    # ( timedelta param is in days )
    return is_between(date, start, end)


def is_soon(date):
    """ Return True if the given date (datetime object) is in the near future.
        Currently this means within 24 hours, but that may change.
    """
    end = datetime.datetime.now() + datetime.timedelta(1)
    start = datetime.datetime.now()

    return is_between(date, start, end)


def is_future(date):
    """ isFuture isn't right, but a lot of code now depends on its behaviour.
        isFuture2 does things correctly and should be phased in over time.

        Return True if the given date (datetime object) is in the future.
    """
    now = datetime.datetime.now()
    if date > now:
        return True
    return False


def is_past(date):
    """ isFuture isn't right, but a lot of code now depends on its behaviour.
        isFuture2 does things correctly and should be phased in over time.

        Return True if the given date (datetime object) is in the past.
    """
    now = datetime.datetime.now()
    if date < now:
        return True
    return False


def get_exam_q(exam, page, user_id):
    """ Find the appropriate exam question for the user.
        Generate it if there isn't one already.
    """
    qid = DB.get_exam_q_by_pos_student(exam, page, user_id)
    if qid is not False:
        return int(qid)
    qid = int(gen_exam_q(exam, page, user_id))
    try:
        qid = int(qid)
        assert qid > 0
    except (ValueError, TypeError, AssertionError):
        L.warn("generateExamQuestion(%s,%s, %s) Failed (returned %s)" % (exam, page, user_id, qid))
        qid = None
    if qid:
        DB.set_q_viewtime(qid)
    return qid


def get_exam_qs(student, exam):
    """ Get the list of exam questions the user has been assigned.
        generate blank ones if needed. """
    numqtemplates = Exams.get_num_questions(exam)
    questions = []
    for position in range(1, numqtemplates + 1):
        question = get_exam_q(exam, position, student)
        if not question:
            question = int(gen_exam_q(exam, position, student))
        questions.append(question)
    return questions


def remark_exam(exam, student):
    """Re-mark the exam using the latest marking. """
    qtemplates = Exams.get_qts(exam)
    examtotal = 0.0
    end = Exams.get_mark_time(exam, student)
    for qtemplate in qtemplates:
        question = DB.get_exam_q_by_qt_student(exam, qtemplate, student)
        answers = DB.get_q_guesses_before_time(question, end)
        try:
            marks = mark_q(question, answers)
        except OaMarkerError:
            L.warn("Marker Error, question %d while re-marking exam %s for student %s!" % (question, exam, student))
            marks = {}
        parts = [int(var[1:]) for var in marks.keys() if re.search("^A([0-9]+)$", var) > 0]
        parts.sort()
        total = 0.0
        for part in parts:
            if marks['C%d' % part] == 'Correct':
                marks['C%d' % part] = "<b><font color='darkgreen'>Correct</font></b>"
            try:
                mark = float(marks['M%d' % part])
            except (ValueError, TypeError, KeyError):
                mark = 0
            total += mark
        DB.update_q_score(question, total)
        #        OaDB.setQuestionStatus(question, 3)    # 3 = marked
        examtotal += total
    Exams.save_score(exam, student, examtotal)
    return examtotal


def remark_prac(question):
    """ Re-mark the practice question and store the score back
        in the questions table.
    """
    answers = DB.get_q_guesses(question)
    try:
        marks = mark_q(question, answers)
    except OaMarkerError:
        return None
    parts = [int(var[1:])
             for var in marks.keys()
             if re.search("^A([0-9]+)$", var) > 0]
    parts.sort()
    total = 0.0
    for part in parts:
        try:
            mark = float(marks['M%d' % part])
        except (ValueError, TypeError, KeyError):
            mark = 0
        total += mark
    DB.update_q_score(question, total)
    DB.set_q_status(question, 3)    # 3 = marked
    return total


def human_dates(start, end, html=True):
    """ Return a string containing a nice human readable description of
        the time period.
        eg. if the start and end are on the same day, it only gives the date
        once.
        If html is set to true, the string may contain HTML formatting codes.
    """
    # Period is in one date.
    if (start.year, start.month, start.day) == (end.year, end.month, end.day):
        if html:
            return "%s, %s to %s" % (start.strftime("%a %b %d %Y"), start.strftime("%I:%M%P"), end.strftime("%I:%M%P"))
        else:
            return "%s to %s" % (start.strftime("%a %b %d %Y, %I:%M%P"), end.strftime("%I:%M%P"))
    # Spread over more than one date.
    if html:
        return "%s to %s" % (start.strftime("%a %b %d %Y, %I:%M%P"), end.strftime("%a %b %d %Y, %I:%M%P"))
    else:
        return "%s to %s" % (start.strftime("%a %b %d %Y, %I:%M%P"), end.strftime("%a %b %d %Y, %I:%M%P"))


def human_date(date):
    """ Return a string containing a nice human readable date/time.
        Miss out the year if it's this year
     """
    today = datetime.datetime.today()
    if today.year == date.year:
        return date.strftime("%b %d, %I:%M%P")

    return date.strftime("%Y %b %d, %I:%M%P")


def date_from_py2js(when):
    """ Convert date from Python datetime object to Javascript friendly
        epoch integer.
    """

    return int(time.mktime(when.timetuple())) * 1000


def sanitize_username(uname):
    """ Take a user provided username and "normalize it" (take out spaces, quotes, etc).
        This is not a security measure, it's more for interoperability with, eg. command
        line tools.
    """

    uname = uname.replace("'", "")
    uname = uname.replace('"', "")
    uname = uname.replace(" ", "")
    return uname
