from hashlib import sha256
import logging
import json
import os
import arrow
import sqlite3
import time

from flask import Flask, request
import requests

from signing.verify import verify_data


class Block:
    def __init__(self, index, transactions,
                 timestamp, previous_hash,
                 nonce=0):

        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.nonce = nonce

    def compute_hash(self):
        """
        A function that return the hash of the block contents.
        """
        block_string = json.dumps(self.__dict__, sort_keys=True)
        return sha256(block_string.encode()).hexdigest()


class Blockchain:
    # difficulty of our PoW algorithm
    difficulty = 2

    def __init__(self):
        self.unconfirmed_transactions = []
        self.chain = []

    def create_genesis_block(self):
        """
        A function to generate genesis block and appends it to
        the chain. The block has index 0, previous_hash as 0, and
        a valid hash.
        """
        amount = 9223372036854775807
        to_address = os.getenv('SPC_MASTER_PK')
        transaction = {'amount': amount,
                       'from_address': '0',
                       'to_address': to_address,
                       'timestamp': arrow.get('1969-12-28 13:37:00+00:00').format(),
                       'status': 1}
        genesis_block = Block(0, [transaction], 0, "0")
        genesis_block.hash = genesis_block.compute_hash()
        app.logger.info(f'create genesisblock: {genesis_block.hash}')
        self.chain.append(genesis_block)

    @property
    def last_block(self):
        return self.chain[-1]

    def restore(self):
        tic = time.perf_counter()
        generated_blockchain = Blockchain()
        generated_blockchain.create_genesis_block()
        conn = sqlite3.connect('blockchain.db')
        c = conn.cursor()
        sql = """
        CREATE TABLE IF NOT EXISTS block (
            i INTEGER PRIMARY KEY,
            v TEXT NOT NULL
        );
        """
        c.execute(sql)
        c.execute('SELECT * FROM block ORDER BY i ASC')
        for b in c.fetchall():
            block_data = json.loads(b[1])
            block = Block(block_data["index"],
                          block_data["transactions"],
                          block_data["timestamp"],
                          block_data["previous_hash"],
                          block_data["nonce"])
            proof = block_data['hash']
            added = generated_blockchain.add_block(block, proof)
            app.logger.info(f'added block {added} {block.index} {block.previous_hash}')
        conn.close()
        self.chain = generated_blockchain.chain
        toc = time.perf_counter()
        app.logger.info(f"restore: {len(self.chain)} blocks in {toc - tic:0.4f}s")


    def preserve_blockchain(self):
        conn = sqlite3.connect('blockchain.db')
        c = conn.cursor()
        c.execute("DELETE FROM block;")
        for block in self.chain:
            if block.index == 0:
                continue
            data = json.dumps(block.__dict__, sort_keys=True)
            insert_sql = f"""
            INSERT INTO block (i, v)
            VALUES (?, ?);
            """
            values = [block.index, data]
            c.execute(insert_sql, values)
        conn.commit()
        conn.close()

    def add_block(self, block, proof):
        """
        A function that adds the block to the chain after verification.
        Verification includes:
        * Checking if the proof is valid.
        * The previous_hash referred in the block and the hash of latest block
          in the chain match.
        """
        previous_hash = self.last_block.hash

        if previous_hash != block.previous_hash:
            return False

        if not Blockchain.is_valid_proof(block, proof):
            return False

        block.hash = proof

        self.chain.append(block)
        return True

    @staticmethod
    def proof_of_work(block):
        """
        Function that tries different values of nonce to get a hash
        that satisfies our difficulty criteria.
        """
        block.nonce = 0

        computed_hash = block.compute_hash()
        while not computed_hash.startswith('0' * Blockchain.difficulty):
            block.nonce += 1
            computed_hash = block.compute_hash()

        return computed_hash

    def add_new_transaction(self, transaction):
        self.unconfirmed_transactions.append(transaction)

    @classmethod
    def is_valid_proof(cls, block, block_hash):
        """
        Check if block_hash is valid hash of block and satisfies
        the difficulty criteria.
        """
        return (block_hash.startswith('0' * Blockchain.difficulty) and
                block_hash == block.compute_hash())

    @classmethod
    def check_chain_validity(cls, chain):
        result = True
        previous_hash = "0"

        for block in chain:
            block_hash = block.hash
            # remove the hash field to recompute the hash again
            # using `compute_hash` method.
            delattr(block, "hash")

            if not cls.is_valid_proof(block, block_hash) or \
               previous_hash != block.previous_hash:
                result = False
                break

            block.hash, previous_hash = block_hash, block_hash

        return result


    def get_balance(self, address):
        balance = 0
        tic = time.perf_counter()
        for block in self.chain:
            for tx in block.transactions:
                if tx['status'] != 1:
                    continue
                if tx['from_address'] == address:
                    balance -= tx['amount']
                elif tx['to_address'] == address:
                    balance += tx['amount']
        toc = time.perf_counter()
        app.logger.info(f"get_balance: {address} {balance} in {toc - tic:0.4f}s")
        return balance
    
    def validate_block_transactions(self, transactions):
        valid_transactions = []
        current_block_balances = {}

        for tx in transactions:

            from_address = tx['from_address']
            to_address = tx['to_address']
            amount = tx['amount']

            from_balance = self.get_balance(from_address)
            from_balance += current_block_balances.get(from_address, 0)

            if from_balance >= amount:

                cbb_from = current_block_balances.get(from_address, 0)
                cbb_to = current_block_balances.get(to_address, 0)
                current_block_balances[from_address] = cbb_from - amount
                current_block_balances[to_address] = cbb_to - amount

                tx['status'] = 1
                valid_transactions.append(tx)

        return valid_transactions

    def mine(self):
        """
        This function serves as an interface to add the pending
        transactions to the blockchain by adding them to the block
        and figuring out Proof Of Work.
        """
        if not self.unconfirmed_transactions:
            return False

        last_block = self.last_block
        valid_transactions = self.validate_block_transactions(
            self.unconfirmed_transactions)

        new_block = Block(index=last_block.index + 1,
                          transactions=valid_transactions,
                          timestamp=arrow.utcnow().format(),
                          previous_hash=last_block.hash)

        proof = self.proof_of_work(new_block)
        self.add_block(new_block, proof)
        self.preserve_blockchain()

        self.unconfirmed_transactions = []

        return True

def setup_logger():
    log_level = logging.INFO
    for handler in app.logger.handlers:
        app.logger.removeHandler(handler)
    root = os.path.dirname(os.path.abspath(__file__))
    logdir = os.path.join(root, 'logs')
    if not os.path.exists(logdir):
        os.mkdir(logdir)
    log_file = os.path.join(logdir, 'app.log')
    handler = logging.FileHandler(log_file)
    handler.setLevel(log_level)
    app.logger.addHandler(handler)
    app.logger.setLevel(log_level)

app = Flask(__name__)
app.url_map.strict_slashes = False
setup_logger()
# the node's copy of blockchain
blockchain = Blockchain()
blockchain.restore()
if len(blockchain.chain) == 0:
    blockchain.create_genesis_block()

# the address to other participating members of the network
peers = set()


# endpoint to submit a new transaction. This will be used by
# our application to add new data (posts) to the blockchain
@app.route('/new_transaction', methods=['POST'])
def new_transaction():

    tx_data = request.get_json()
    required_fields = ["public_key", "message"]

    for field in required_fields:
        if not field in tx_data:
            return "Invalid transaction data", 404

    message = tx_data['message']
    public_key = tx_data['public_key']
    tx_data = verify_data(data_hex=message,
                          key_hex=public_key)
    tx_data = json.loads(tx_data)
    required_fields = ["to_address", "from_address", "amount"]
    for field in required_fields:
        if not field in tx_data:
            return "Invalid transaction data", 404

    tx_data["amount"] = int(tx_data["amount"])
    tx_data["timestamp"] = arrow.utcnow().format()
    tx_data["status"] = 0

    blockchain.add_new_transaction(tx_data)
    app.logger.info(f"transfer: {public_key} {message}")

    return "OK", 200


# endpoint to return the node's copy of the chain.
# Our application will be using this endpoint to query
# all the posts to display.
@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = []
    for block in blockchain.chain:
        chain_data.append(block.__dict__)
    return json.dumps({"length": len(chain_data),
                       "chain": chain_data,
                       "peers": list(peers)})


def _update_balances(balances, from_address,
                     to_address, amount):
    balances[from_address] = balances.get(from_address, 0) - amount
    balances[to_address] = balances.get(to_address, 0) + amount


@app.route('/transactions/', methods=['GET'])
@app.route('/transactions/<address>', methods=['GET'])
def get_transactions(address=None):
    balances = {}
    transactions = []
    for block in blockchain.chain:
        for tx in block.transactions:
            if address:
                if tx['from_address'] != address\
                   and tx['to_address'] != address:
                    continue

            if tx['status'] == 1:
                _update_balances(balances, tx['from_address'],
                                 tx['to_address'], tx['amount'])
                transactions.append(tx)
    return json.dumps({"length": len(transactions),
                       "balances": balances,
                       "transactions": transactions})

# endpoint to request the node to mine the unconfirmed
# transactions (if any). We'll be using it to initiate
# a command to mine from our application itself.
@app.route('/mine', methods=['GET'])
def mine_unconfirmed_transactions():
    result = blockchain.mine()
    if not result:
        return "No transactions to mine"
    else:
        # Making sure we have the longest chain before announcing to the network
        chain_length = len(blockchain.chain)
        consensus()
        if chain_length == len(blockchain.chain):
            # announce the recently mined block to the network
            announce_new_block(blockchain.last_block)
        return "Block #{} is mined.".format(blockchain.last_block.index)


# endpoint to add new peers to the network.
@app.route('/register_node', methods=['POST'])
def register_new_peers():
    node_address = request.get_json()["node_address"]
    if not node_address:
        return "Invalid data", 400

    # Add the node to the peer list
    chain = get_chain()
    peers.add(node_address)

    # Return the consensus blockchain to the newly registered node
    # so that he can sync
    return chain


@app.route('/register_with', methods=['POST'])
def register_with_existing_node():
    """
    Internally calls the `register_node` endpoint to
    register current node with the node specified in the
    request, and sync the blockchain as well as peer data.
    """
    node_address = request.get_json()["node_address"]
    if not node_address:
        return "Invalid data", 400

    data = {"node_address": request.host_url}
    headers = {'Content-Type': "application/json"}

    # Make a request to register with remote node and obtain information
    response = requests.post(node_address + "/register_node",
                             data=json.dumps(data), headers=headers)

    if response.status_code == 200:
        global blockchain
        global peers
        # update chain and the peers
        chain_dump = response.json()['chain']
        blockchain = create_chain_from_dump(chain_dump)
        blockchain.preserve_blockchain()
        peers.add(node_address)
        peers.update(response.json()['peers'])
        return "Registration successful", 200
    else:
        # if something goes wrong, pass it on to the API response
        return response.content, response.status_code


def create_chain_from_dump(chain_dump):
    generated_blockchain = Blockchain()
    generated_blockchain.create_genesis_block()
    for idx, block_data in enumerate(chain_dump):
        if idx == 0:
            continue  # skip genesis block
        block = Block(block_data["index"],
                      block_data["transactions"],
                      block_data["timestamp"],
                      block_data["previous_hash"],
                      block_data["nonce"])
        proof = block_data['hash']
        added = generated_blockchain.add_block(block, proof)
        if not added:
            raise Exception("The chain dump is tampered!!")
    return generated_blockchain


# endpoint to add a block mined by someone else to
# the node's chain. The block is first verified by the node
# and then added to the chain.
@app.route('/add_block', methods=['POST'])
def verify_and_add_block():
    block_data = request.get_json()
    block = Block(block_data["index"],
                  block_data["transactions"],
                  block_data["timestamp"],
                  block_data["previous_hash"],
                  block_data["nonce"])

    proof = block_data['hash']
    added = blockchain.add_block(block, proof)

    if not added:
        return "The block was discarded by the node", 400

    blockchain.preserve_blockchain()
    return "Block added to the chain", 201


# endpoint to query unconfirmed transactions
@app.route('/pending_tx')
@app.route('/pending_tx/<address>')
def get_pending_tx(address=None):
    if not address:
        return json.dumps(blockchain.unconfirmed_transactions)
    else:
        transactions = []
        for tx in blockchain.unconfirmed_transactions:
            if tx['from_address'] == address or tx['to_address'] == address:
                transactions.append(tx)
        return json.dumps(transactions)


def consensus():
    """
    Our naive consnsus algorithm. If a longer valid chain is
    found, our chain is replaced with it.
    """
    global blockchain

    longest_chain = None
    current_len = len(blockchain.chain)

    remove_nodes = []
    for node in peers:
        try:
            response = requests.get('{}chain'.format(node))
            length = response.json()['length']
            chain = response.json()['chain']
            if length > current_len and blockchain.check_chain_validity(chain):
                current_len = length
                longest_chain = chain
        except requests.exceptions.ConnectionError as e:
            remove_nodes.append(node)

    for node in remove_nodes:
        peers.remove(node)

    if longest_chain:
        blockchain = longest_chain
        return True

    return False


def announce_new_block(block):
    """
    A function to announce to the network once a block has been mined.
    Other blocks can simply verify the proof of work and add it to their
    respective chains.
    """

    error_peers = []

    for peer in peers:
        try:
            url = f"{peer}add_block"
            headers = {'Content-Type': "application/json"}
            requests.post(url,
                        data=json.dumps(block.__dict__, sort_keys=True),
                        headers=headers)
        except Exception as e:
            error_peers.append(peer)

    for ep in error_peers:
        peers.remove(ep)

# Uncomment this line if you want to specify the port number in the code
# app.run(debug=True, port=8000, host='0.0.0.0')
