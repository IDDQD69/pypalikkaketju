import datetime
import json

import requests
from flask import render_template, redirect, request
from flask import jsonify

from app import app

# The node with which our application interacts, there can be multiple
# such nodes as well.
CONNECTED_NODE_ADDRESS = "http://127.0.0.1:8000"

transactions = []


def fetch_chain():
    """
    Function to fetch the chain from a blockchain node, parse the
    data and store it locally.
    """
    get_chain_address = "{}/chain".format(CONNECTED_NODE_ADDRESS)
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

@app.route('/wallet')
def wallet():
    return render_template('wallet.html')

@app.route('/')
def index():
    fetch_chain()
    return render_template('index.html',
                           title='YourNet: Decentralized '
                                 'content sharing',
                           transactions=transactions,
                           node_address=CONNECTED_NODE_ADDRESS,
                           readable_time=timestamp_to_string)


@app.route('/submit', methods=['POST'])
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


def timestamp_to_string(epoch_time):
    return datetime.datetime.fromtimestamp(epoch_time).strftime('%H:%M')
