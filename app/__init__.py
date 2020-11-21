from os import getenv
from flask import Flask

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config["APPLICATION_ROOT"] = getenv('SPC_PREFIX', '')

from app import views
