"""Vercel serverless entrypoint.

@vercel/python imports this module and serves the WSGI callable it finds in
`app`. The sys.path insert makes `config`, `documents`, etc. importable the
same way they are when manage.py runs from the backend/ directory.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()
