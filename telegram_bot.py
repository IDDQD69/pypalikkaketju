
from telegram import Update
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import Filters
from telegram.ext import CallbackContext
from telegram.ext import JobQueue

from peewee import SqliteDatabase
from peewee import Model
from peewee import CharField
from peewee import DateTimeField
from peewee import DoubleField
from peewee import IntegerField

from datetime import datetime as dt

from nacl.public import PrivateKey
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder
from nacl.encoding import Base64Encoder
from nacl.encoding import URLSafeBase64Encoder
from nacl.bindings.crypto_sign import crypto_sign_ed25519_sk_to_pk
from nacl.bindings.crypto_sign import crypto_sign_keypair

import requests
import json
import nacl.secret
import nacl.utils


from os import environ

# pip install python-telegram-bot
# pip install peewee

db = SqliteDatabase('spc.db')

class Roll(Model):
    user_id = IntegerField()
    count = IntegerField()

    class Meta:
        database = db

class Transaction(Model):
    to_address = CharField()
    from_address = CharField()
    amount = IntegerField()
    timestamp = DateTimeField()

    class Meta:
        database = db

class Address(Model):
    user_id = IntegerField()
    username = CharField()
    address = CharField()

    class Meta:
        database = db

    def __str__(self):
        return f'{self.user_id} {self.username} {self.address}'


def _create_tables():
    with db:
        db.create_tables([Roll, Transaction, Address])

def _get_keys(secret_key):
    public_key = crypto_sign_ed25519_sk_to_pk(bytes.fromhex(secret_key))
    return secret_key, public_key.hex()

_create_tables()
token = environ['tbot_api']
spc_url = environ['spc_url']
spc_wallet = environ['spc_wallet']

secret_key, public_key = _get_keys(spc_wallet)

updater = Updater(token, use_context=True)


def address(update: Update, context: CallbackContext) -> None:
    arguments = update.message.text.split(' ')
    if len(arguments) == 1:
        text = 'Osoitteet:\n'
        for a in Address.select():
            text += f'{a.username} {a.address}\n\n'
        update.message.reply_text(text)
    if len(arguments) == 2:
        user = update.effective_user
        Address.delete()\
               .where(Address.user_id==user.id)\
               .execute()
        username = user.first_name
        if user.last_name:
            username += f' {user.last_name}'
        Address.create(user_id=update.effective_user.id,
                       username=username,
                       address=arguments[1])
        update.message.reply_text('Osoite lisätty!')

def message(update, context):
    print('update')

updater.dispatcher.add_handler(CommandHandler(command='osoite',
                                              filters=Filters.all,
                                              callback=address))

def _get_transactions():
    transactions = []
    get_chain_address = f"{spc_url}/transactions/{public_key}"
    print('get chain address', get_chain_address)
    response = requests.get(get_chain_address)
    if response.status_code == 200:
        data = json.loads(response.content)
        print('data', data['transactions'])


def job_callback(st):
    print('job callback', st)
    _get_transactions()

jobs = JobQueue()
jobs.set_dispatcher(updater.dispatcher)
jobs.run_repeating(callback=job_callback, interval=10)
jobs.start()

updater.start_polling()
updater.idle()
