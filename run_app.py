from app import app
from os import getenv

hostname = getenv('SPC_HOSTNAME', 'localhost')
port = getenv('SPC_PORT', 5000)
debug = getenv('SPC_DEBUG', False)

app.run(debug=debug,
        host=hostname,
        port=port)