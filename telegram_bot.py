
import datetime
import requests
import json
import arrow
import logging
import os

from telegram import Update
from telegram.ext import Updater
from telegram.ext import MessageHandler
from telegram.ext import Filters
from telegram.ext import JobQueue

from peewee import SqliteDatabase
from peewee import DoesNotExist
from peewee import Model
from peewee import CharField
from peewee import DateTimeField
from peewee import IntegerField

from nacl.bindings.crypto_sign import crypto_sign_ed25519_sk_to_pk

db = SqliteDatabase('database/spc.db')


class Dice(Model):
    user_id = IntegerField()
    emoji = CharField()
    value = IntegerField()
    bet = IntegerField()
    win = IntegerField()
    datetime = DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = db

    def __str__(self):
        return f'{self.emoji} {self.bet} {self.win}'

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


class SPCTelegramBot:

    def __init__(self, logger):
        self.logger = logger

        self.token = os.environ['tbot_api']
        self.spc_url = os.environ['spc_url']
        self.spc_wallet = os.environ['spc_wallet']

        self._create_tables()

        self.roll_messages = []
        self.secret_key, self.public_key = self._get_keys(self.spc_wallet)
        self.updater = Updater(self.token, use_context=True)

        msg_handler = MessageHandler(filters=Filters.text,
                                     callback=self.message_callback)
        dice_handler = MessageHandler(filters=Filters.dice,
                                      callback=self.dice_callback)
        self.updater.dispatcher.add_handler(msg_handler)
        self.updater.dispatcher.add_handler(dice_handler)

        jobs = JobQueue()
        jobs.set_dispatcher(self.updater.dispatcher)
        jobs.run_repeating(callback=self.job_callback, interval=10)
        jobs.run_repeating(callback=self.message_job_callback, interval=1)
        jobs.start()

        self.updater.start_polling()
        self.updater.idle()

    @staticmethod
    def _create_tables():
        with db:
            db.create_tables([Roll, Transaction,
                              Address, Dice])

    @staticmethod
    def _get_keys(secret_key):
        public_key = crypto_sign_ed25519_sk_to_pk(bytes.fromhex(secret_key))
        return secret_key, public_key.hex()

    @staticmethod
    def _get_roll(user_id):
        try:
            return Roll.get(Roll.user_id == user_id)
        except DoesNotExist:
            return Roll.create(
                user_id=user_id,
                bet=0,
                balance=0)

    @staticmethod
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

    def cmd_roll(self, update: Update) -> None:
        arguments = update.message.text.split(' ')
        user_id = update.effective_user.id
        try:
            roll = self._get_roll(user_id)
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

    @staticmethod
    def get_roll_message(update, dice, bet, new_balance, win_value):
        return {
            'timestamp': arrow.get().shift(seconds=2).datetime,
            'update': update,
            'win_value': win_value,
            'new_balance': new_balance
        }

    def get_help_text(self):

        return (
            'komennot: \n'
            '!osoite -- listaa osoitteet \n'
            '!osoite <julkinen osoite> -- lisää oma osoitteesi listaan \n\n'
            'Slots! \n'
            'Lisää osoitteesi komennolla !osoite <julkinen osoite> \n'
            'Lähetä SPC osoitteeseen: \n'
            f'{self.public_key} \n\n'
            'https://ajnieminen.kapsi.fi/spc/wallet\n\n'
            'Varat ilmestyvät pelitilillesi muutamassa minuutissa. \n\n'
            '!roll -- näet tilisi tiedot.\n'
            '!roll bet <summa> -- aseta haluamasi panos'
        )

    def dice_callback(self, update, context):
        self.handle_dice(update)

    def message_callback(self, update, context):
        logger.info(f'message_callback: {update}')
        args = update.message.text.lower().split(' ')
        if args[0] == '!help':
            update.message.reply_text(self.get_help_text())
        elif args[0] == '!osoite':
            self.cmd_address(update)
        elif args[0] == '!roll':
            self.cmd_roll(update)

    def handle_dice(self, update):

        if update.message.forward_from is not None:
            return

        logger.info(f'handle_dice: {update}')
        user_id = update.effective_user.id
        dice = update.message.dice
        roll = self._get_roll(user_id)

        dice_bet = roll.bet
        win_value = 0

        for d in Dice.select():
            print('d', d)

        if '🎰' == dice.emoji and roll.bet > 0:
            if roll.balance >= roll.bet:
                # 43 lemonparty
                # 22 rypaleet
                # 1 bar
                # 64 777
                if dice.value in [43, 22, 1]:
                    win_value = roll.bet * 25
                elif dice.value == 64:
                    win_value = roll.bet * 75

                new_balance = roll.balance - roll.bet + win_value
                roll.balance = new_balance
                roll.save()

                message = self.get_roll_message(update, dice,
                                                roll.bet, new_balance,
                                                win_value)
                self.roll_messages.append(message)

                if new_balance <= 0:
                    update.message.reply_text('Ei enää pelimerkkejä.')

        Dice.create(user_id=user_id, emoji=dice.emoji, value=dice.value,
                    bet=dice_bet, win=win_value)

    def _get_transactions(self):
        get_chain_address = f"{self.spc_url}/transactions/{self.public_key}"
        response = requests.get(get_chain_address)
        if response.status_code == 200:
            data = json.loads(response.content)
            return sorted(data['transactions'],
                          key=lambda k: k['timestamp'],
                          reverse=True)
        return []

    @staticmethod
    def _get_default_timestamp():
        arw = arrow.utcnow()
        arw = arw.shift(days=-30)
        return arw.datetime

    @staticmethod
    def _update_timestamp(address, timestamp):
        Transaction\
            .insert(address=address, timestamp=timestamp)\
            .on_conflict('replace')\
            .execute()

    def job_callback(self, context):
        for tx in self._get_transactions():

            if tx['to_address'] != self.public_key or tx['status'] != 1:
                continue

            try:
                address = Address.get(Address.address == tx['from_address'])
            except DoesNotExist:
                continue

            try:
                timestamp = Transaction.get(Transaction.address == address.address).timestamp
            except DoesNotExist:
                timestamp = self._get_default_timestamp()

            tx_timestamp = arrow.get(tx['timestamp']).datetime
            if arrow.get(timestamp).datetime < tx_timestamp:
                self._update_timestamp(address.address, tx_timestamp)
                amount = tx['amount']
                roll = self._get_roll(address.user_id)
                roll.balance = roll.balance + amount
                roll.save()

    def message_job_callback(self, context):
        new_messages = []
        now_time = arrow.get().datetime
        for msg in self.roll_messages:
            if now_time < msg['timestamp']:
                new_messages.append(msg)
                continue

            update = msg['update']
            if msg['win_value'] > 0:
                message_string = f'-- VOITTO {msg["win_value"]} SPC --'
                update.message.reply_text(message_string)
        self.roll_messages = new_messages


if __name__ == '__main__':
    # setup logging

    root = os.path.dirname(os.path.abspath(__file__))
    logdir = os.path.join(root, 'logs')
    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logfile = os.path.join(logdir, 'telegram_bot.log')
    logging.basicConfig(filename=logfile, level=logging.ERROR)

    logger = logging.getLogger('telegram_bot')
    logger.setLevel(logging.INFO)

    # start bot
    bot = SPCTelegramBot(logger)
