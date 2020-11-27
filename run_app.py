from app import app
from os import getenv

hostname = getenv('SPC_HOSTNAME', 'http://localhost/')
port = getenv('SPC_PORT', 5000)
debug = getenv('SPC_DEBUG', False)
application_root = getenv('SPC_APPLICATION_ROOT', '')

app.run(debug=debug,
        hostname=hostname,
        port=port)

if application_root and len(application_root):
    app.config["APPLICATION_ROOT"] = "/spc"
