import datetime
import json

from io import BytesIO
from os import getenv

import pagan

import requests

from jinja2 import Markup
from flask import render_template, request
from flask import jsonify
from flask import send_file

from PIL import Image

from app import app

from signing.verify import verify_data

# The node with which our application interacts, there can be multiple
# such nodes as well.
CONNECTED_NODE_ADDRESS = getenv('SPC_NODE')
PREFIX = getenv('SPC_APPLICATION_ROOT', '')

transactions = []


@app.context_processor
def transaction_processor():

    def ts_js(tx):
        return Markup(f'''
        <script>
          document.write(
            moment("{tx["timestamp"]}").format('L') + ' ' +
            moment("{tx["timestamp"]}").format('LT')
          );
        </script>''')

    def timestamp(tx):
        return f'{tx["timestamp"]}'

    return {'timestamp': timestamp,
            'ts_js': ts_js}


def fetch_chain():
    """
    Function to fetch the chain from a blockchain node, parse the
    data and store it locally.
    """
    get_chain_address = f"{CONNECTED_NODE_ADDRESS}/chain"
    response = requests.get(get_chain_address)
    if response.status_code == 200:
        content = []
        chain = json.loads(response.content)
        for block in chain["chain"]:
            for tx in block["transactions"]:
                tx["index"] = block["index"]
                tx["hash"] = block["previous_hash"]
                content.append(tx)

        global transactions
        transactions = sorted(content, key=lambda k: k['timestamp'],
                       reverse=True)


@app.route(f'{PREFIX}/directory')
def get_directory():
    return jsonify({})


@app.route(f'{PREFIX}/directory', methods=['POST'])
def set_directory():
    data = request.get_json()
    public_key = data['public_key']
    signed_public_key = data['signed_public_key']
    given_public_key = verify_data(data_hex=signed_public_key, key_hex=public_key)
    bytes.decode(given_public_key)
    return jsonify(data)


@app.route(f'{PREFIX}/wallet')
def wallet():
    return render_template('wallet.html', prefix=PREFIX)


@app.route(f'{PREFIX}/account/')
@app.route(f'{PREFIX}/account/<address>')
def account(address=None):
    txs = []
    balances = {}
    address = address if address else ''
    get_chain_address = f"{CONNECTED_NODE_ADDRESS}/transactions/{address}"
    response = requests.get(get_chain_address)
    if response.status_code == 200:
        data = json.loads(response.content)
        balances = data['balances']
        txs = sorted(data['transactions'],
                     key=lambda k: k['timestamp'],
                     reverse=True)
    return render_template('account.html',
                           prefix=PREFIX,
                           address=address,
                           balances=balances,
                           transactions=txs)


@app.route(f'{PREFIX}/transactions/<address>', methods=['GET'])
def get_transactions(address):
    get_chain_address = f"{CONNECTED_NODE_ADDRESS}/transactions/{address}"
    response = requests.get(get_chain_address)
    return response.text


@app.route(f'{PREFIX}/pending_tx')
@app.route(f'{PREFIX}/pending_tx/<address>')
def get_pending_tx(address=None):
    address = address if address else ''
    get_chain_address = f"{CONNECTED_NODE_ADDRESS}/pending_tx/{address}"
    response = requests.get(get_chain_address)
    return response.text


@app.route(f'{PREFIX}/')
def index():
    fetch_chain()
    return render_template('index.html',
                           prefix=PREFIX,
                           title='Seppocoin palikkaketju',
                           transactions=transactions,
                           node_address=CONNECTED_NODE_ADDRESS,
                           readable_time=timestamp_to_string)


@app.route(f'{PREFIX}/submit', methods=['POST'])
def submit_textarea():
    """
    Endpoint to create a new transaction via our application.
    """
    # Submit a transaction
    new_tx_address = f"{CONNECTED_NODE_ADDRESS}/new_transaction"
    result = requests.post(new_tx_address,
                           json=request.get_json(),
                           headers={'Content-type': 'application/json'})

    return jsonify({'status_code': result.status_code,
                    'status_text': result.text})


def serve_pil_image(pil_img):
    img_io = BytesIO()
    pil_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


@app.route(f'{PREFIX}/hash_img/')
@app.route(f'{PREFIX}/hash_img/<value>')
def get_hash_img(value=None):
    if value is None or len(value) <= 0:
        im = Image.open("app/static/stare.png")
        return serve_pil_image(im)
    p = pagan.Avatar(value, pagan.SHA256)
    return serve_pil_image(p.img)


def timestamp_to_string(epoch_time):
    return datetime.datetime.fromtimestamp(epoch_time).strftime('%H:%M')
