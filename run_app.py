from app import app

app.run(debug=True,
        ssl_context=('server.crt', 'server.key'))
