
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

import datetime
import arrow

from os import environ

# pip install python-telegram-bot
# pip install peewee
#
# export tbot_api=''
# export spc_url=''
# export spc_wallet=''

db = SqliteDatabase('spc.db')

roll_messages = []

class Dice(Model):
    user_id = IntegerField()
    emoji = CharField()
    value = IntegerField()
    datetime = DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = db

class Roll(Model):
    user_id = IntegerField(primary_key=True)
    bet = IntegerField()
    balance = IntegerField()

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
        db.create_tables([Roll, Transaction,
                          Address, Dice])

def _get_keys(secret_key):
    public_key = crypto_sign_ed25519_sk_to_pk(bytes.fromhex(secret_key))
    return secret_key, public_key.hex()

def _get_roll(user_id):
    try:
        return Roll.get(Roll.user_id==user_id)
    except Exception as e:
        return Roll.create(user_id=user_id,
                           bet=0,
                           balance=0)

_create_tables()
token = environ['tbot_api']
spc_url = environ['spc_url']
spc_wallet = environ['spc_wallet']

secret_key, public_key = _get_keys(spc_wallet)

updater = Updater(token, use_context=True)


def cmd_address(update: Update) -> None:
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


def cmd_roll(update: Update) -> None:
    arguments = update.message.text.split(' ')
    user_id = update.effective_user.id
    try:
        roll = _get_roll(user_id)
        if (len(arguments) > 2 and
            arguments[1] == 'bet'):

            roll.bet = int(arguments[2])
            roll.save()
        address = Address.get(Address.user_id==user_id)
        return_message = (
            '-- Tilisi tiedot -- \n'
            f'Peliti: {roll.balance} SPC\n'
            f'Panos: {roll.bet}\n'
        )
        update.message.reply_text(return_message)
    except Exception as e:
        print(e)
        update.message.reply_text('Osoitetta ei lisätty.')

def get_roll_message(update, dice, bet, new_balance):
    # 43 lemonparty
    # 22 rypaleet
    # 1 bar
    # 64 777
    win_value = 0
    if dice.value in [43, 22, 1]:
        win_value = bet * 5
    elif dice.value == 64:
        win_Value = bet * 10
    return {
        'timestamp': arrow.get().shift(seconds=3).datetime,
        'update': update,
        'win_value': win_value,
        'new_balance': new_balance
    }

def get_help_text():
    return (
        'komennot: \n'
        '!osoite -- listaa osoitteet \n'
        '!osoite <julkinen osoite> -- lisää oma osoitteesi listaan \n\n'
        'Slots! \n'
        'Lisää osoitteesi komennolla !osoite <julkinen osoite> \n'
        'Lähetä SPC osoitteeseen: \n'
        f'{public_key} \n\n'
        'Varat ilmestyvät pelitilillesi muutamassa minuutissa. '
        'Voit tarkistaa tilin komennolla !roll \n'
        '!roll -- näet tilisi tiedot.'
        '!roll bet <summa> -- aseta haluamasi panos'
    )

def message(update, context):
    if update.message.text:
        args = update.message.text.split(' ')
        if args[0] == '!help':
            update.message.reply_text(get_help_text())
        elif args[0] == '!osoite':
            cmd_address(update)
        elif args[0] == '!roll':
            cmd_roll(update)
    if update.message.dice:
        handle_dice(update)

def handle_dice(update):
    try:
        user_id = update.effective_user.id
        dice = update.message.dice
        roll = _get_roll(user_id)
        if '🎰' == dice.emoji:
            if roll_count > 0:
                new_roll_count = roll_count - 1
                _set_roll_count(user_id, new_roll_count)
                message = get_roll_message(update, dice, new_roll_count)
                Dice.create(user_id=user_id, emoji=dice.emoji, value=dice.value)
                global roll_messages
                roll_messages.append(message)
    except:
        pass


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
    arw = arw.shift(days=-30)
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
        if tx['to_address'] != public_key:
            continue
        try:
            print('we move on')
            address = Address.get(Address.address==tx['from_address'])
            timestamp = timestamps.get(address.address, _get_default_timestamp())
            tx_timestamp = arrow.get(tx['timestamp'])
            # TODO ASSING TX TIMESTAMP TO USER
            print('tx', timestamp, tx_timestamp)
            if timestamp < tx_timestamp:
                print('no new transactions for ', address.address)
                continue
            else:
                amount = tx['amount']
                roll = _get_roll(address.user_id)
                roll.balance = roll.balance + amount
                roll.save()
        except Exception as e:
            print('e', e)
            pass

def message_callback(st):
    global roll_messages
    for msg in roll_messages:
        print('msg', msg)

updater.dispatcher.add_handler(
    MessageHandler(filters=Filters.all,
                   callback=message))

jobs = JobQueue()
jobs.set_dispatcher(updater.dispatcher)
jobs.run_repeating(callback=job_callback, interval=10)
jobs.run_repeating(callback=message_callback, interval=1)
jobs.start()

updater.start_polling()
updater.idle()
