
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

import arrow

from os import environ

# pip install python-telegram-bot
# pip install peewee

db = SqliteDatabase('spc.db')

ROLL_PRICE = 100


class Roll(Model):
    user_id = IntegerField(primary_key=True)
    count = IntegerField()

    class Meta:
        database = db

class Transaction(Model):
    address = CharField(primary_key=True)
    timestamp = DateTimeField()

    class Meta:
        database = db

class Address(Model):
    user_id = IntegerField(primary_key=True)
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

def _get_roll_count(user_id):
    try:
        return Roll.get(Roll.user_id==user_id).count
    except Exception as e:
        return 0

def _set_roll_count(user_id, count):
    try:
        Roll\
            .insert(user_id=user_id, count=count)\
            .on_conflict('replace')\
            .execute()
        return True
    except Exception as e:
        print('e', e)
        return False

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


def roll(update: Update, context: CallbackContext) -> None:
    arguments = update.message.text.split(' ')
    try:
        user_id = update.effective_user.id
        address = Address.get(Address.user_id==user_id)
        roll_count = _get_roll_count(user_id)
        update.message.reply_text(f'Pelejä jäljellä: {roll_count}')
    except Exception as e:
        update.message.reply_text('Osoitetta ei lisätty.')

def message(update, context):
    try:
        user_id = update.effective_user.id
        if '🎰' == update.message.dice.emoji:
            roll_count = _get_roll_count(user_id)
            if roll_count > 0:
                _set_roll_count(user_id, roll_count - 1)
                print('rolled!')
            else:
                print('no rolls')
            print('update', update.message.dice)
    except:
        pass


updater.dispatcher.add_handler(MessageHandler(filters=Filters.all,
                                              callback=message))
updater.dispatcher.add_handler(CommandHandler(command='osoite',
                                              filters=Filters.all,
                                              callback=address))
updater.dispatcher.add_handler(CommandHandler(command='roll',
                                              filters=Filters.all,
                                              callback=roll))

def _get_transactions():
    transactions = []
    get_chain_address = f"{spc_url}/transactions/{public_key}"
    response = requests.get(get_chain_address)
    if response.status_code == 200:
        data = json.loads(response.content)
        return sorted(data['transactions'],
                      key=lambda k: k['timestamp'],
                      reverse=True)
    return []

def _get_default_timestamp():
    arw = arrow.utcnow()
    arw = arw.shift(days=-1)
    return arw.datetime

def _get_address_timestamps():
    values = {}
    for tx in Transaction.select():
        values[tx.address] = tx.timestamp
    return values

def _update_timestamp(address, timestamp):
    Transaction\
        .insert(address=address, timestamp=timestamp)\
        .on_conflict('replace')\
        .execute()


def job_callback(st):
    timestamps = _get_address_timestamps()
    for tx in _get_transactions():
        try:
            address = Address.get(Address.address==tx['from_address'])
            timestamp = timestamps.get(address.address, _get_default_timestamp())
            tx_timestamp = arrow.get(tx['timestamp'])
            if timestamp > tx_timestamp:
                continue
            else:
                amount = tx['amount']
                new_rolls = int(amount / ROLL_PRICE)
                old_rolls = _get_roll_count(address.user_id)
                print('new rolls', new_rolls, 'old rolls', old_rolls)
                _set_roll_count(address.user_id, new_rolls + old_rolls)
        except Exception as e:
            pass

jobs = JobQueue()
jobs.set_dispatcher(updater.dispatcher)
jobs.run_repeating(callback=job_callback, interval=10)
jobs.start()

updater.start_polling()
updater.idle()
