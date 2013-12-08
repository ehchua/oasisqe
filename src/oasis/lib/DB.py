# -*- coding: utf-8 -*-

# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" OaDB.py
    This provides a collection of methods for accessing the database.
    If the database is changed to something other than postgres, this
    is where to start. Since this has grown so large, parts of it are
    being broken off and put in db/*.py
"""

from logging import log, INFO, WARN, ERROR


# Global dbpool
import OaConfig
import Pool

# Cache stuff on local drives to save our poor database
fileCache = Pool.fileCache(OaConfig.cachedir)


def get_db_version():
    """ Return an string representing the database version
        If it's too old to have a configuration field, then use some heuristics.
    """

    # We have a setting, easy
    try:
        ret = run_sql("""SELECT "value"
                         FROM config
                         WHERE "name" = 'dbversion';""", quiet=True)
        if ret:
            return ret[0][0]
    except psycopg2.DatabaseError:
        pass

    # We don't have a setting, need to figure it out
    try:  # questionflags was removed for 3.9.1
        ret = run_sql("SELECT 1 FROM questionflags;", quiet=True)
        if isinstance(ret, list):
            return "3.6"

    except psycopg2.DatabaseError:
        pass

    try:  # one of the very original fields
        ret = run_sql("""SELECT 1 from users;""")
        if ret:
            return "3.9.1"
    except psycopg2.DatabaseError:
        pass

    # No database at all?
    return "unknown"


def get_db_size():
    """ Find out how much space the DB is taking
        Return as a list of  [  [tablename, size] , ... ]
    """

    # Query from   http://wiki.postgresql.org/wiki/Disk_Usage
    sql = """SELECT nspname || '.' || relname AS "relation",
                    pg_size_pretty(pg_total_relation_size(C.oid)) AS "total_size"
             FROM pg_class C
             LEFT JOIN pg_namespace N ON (N.oid = C.relnamespace)
             WHERE nspname NOT IN ('pg_catalog', 'information_schema')
               AND C.relkind <> 'i'
               AND nspname !~ '^pg_toast'
             ORDER BY pg_total_relation_size(C.oid) DESC
             LIMIT 10;
    """

    ret = run_sql(sql)
    sizes = []
    for row in ret:
        sizes.append([row[0], row[1]])

    return sizes

