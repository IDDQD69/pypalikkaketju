from os import getenv
from flask import Flask

application_root = getenv('SPC_APPLICATION_ROOT', '')

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config["APPLICATION_ROOT"] = application_root

from app import views
