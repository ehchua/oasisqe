# -*- coding: utf-8 -*-
#
# This code is under the GNU Affero General Public License
# http://www.gnu.org/licenses/agpl-3.0.html

""" Miscellaneous utility functions
"""

import random

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

