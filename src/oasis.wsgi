# -*- coding: utf-8 -*-

"""
     WSGI wrapper for OASIS. This should be called from a web server that
     supports WSGI.
"""

import sys
import os

sys.path.append(os.path.dirname(__file__))

import oasis

application = oasis.app
