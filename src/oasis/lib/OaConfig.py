# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

"""Controls various configuration setups in Oasis.
   defaults are read from "defaults.ini" in the same directory as this file.

   Site configuration info should be put in an .INI file in /etc/oasisqe.ini
"""

import os
import sys
import logging

from ConfigParser import SafeConfigParser

cp = SafeConfigParser()

mydir = os.path.dirname(os.path.realpath(__file__))

if not cp.read(os.path.join(os.path.sep, mydir, "defaults.ini")):
    sys.exit("Unable to read configuration defaults %s/defaults.ini" % mydir)

cp.read([os.path.join(mydir, 'defaults.ini'), os.path.join(os.path.sep, 'etc', 'oasisqe.ini')])

parentURL = cp.get("web", "url")
statichost = cp.get("web", "statichost")
staticpath = cp.get("web", "staticpath")
default = cp.get("web", "default")
theme_path = cp.get("web", "theme_path")
staticURL = os.path.join(statichost, staticpath)
homedir = cp.get("app", "homedir")
secretkey = cp.get("app", "secretkey")
admin_list = cp.get("app", "email_admins")
smtp_server = cp.get("app", "smtp_server")

if len(admin_list):
    email_admins = admin_list
else:
    email_admins = ()
cachedir = cp.get("cache", "cachedir")

dbhost = cp.get("db", "host")
dbuname = cp.get("db", "uname")
dbname = cp.get("db", "dbname")
dbpass = cp.get("db", "pass")
dbport = cp.get("db", "port")

oasisdbconnectstring = "host=%s port=%s dbname=%s user=%s password='%s'" % \
                       (dbhost, dbport, dbname, dbuname, dbpass)

email = cp.get("web", "email")
contact_url = cp.get("web", "contact_url", False)
if len(contact_url) < 3:
    contact_url = False
memcache_enable = cp.getboolean("cache", "memcache_enable")
uniqueKey = cp.get("cache", "cachekey")

logfile = cp.get("app", "logfile")
_ll = cp.getint("app", "loglevel")
if not (1 <= _ll <= 5):
    loglevel = logging.ERROR
else:
    loglevel = [logging.FATAL, logging.CRITICAL, logging.ERROR, logging.WARN, logging.INFO][_ll - 1]

profile_log = cp.get("app", "profile_log")
feed_path = cp.get("app", "feed_path")
open_registration = cp.getboolean("web", "open_registration")
enable_local_login = cp.getboolean("web", "enable_local_login")
enable_webauth_login = cp.getboolean("web", "enable_webauth_login")
webauth_ignore_domain = cp.getboolean("web", "webauth_ignore_domain")
