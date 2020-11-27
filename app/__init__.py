from os import getenv
from flask import Flask

app = Flask(__name__)
app.url_map.strict_slashes = False

from app import views
