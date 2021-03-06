import binascii
import datetime
import requests
import json
import arrow
import logging
import os

import numpy as np

from telegram import Bot
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

from signing.sign import sign_data

from nacl.bindings.crypto_sign import crypto_sign_ed25519_sk_to_pk, crypto_sign_open, crypto_sign_keypair

db = SqliteDatabase('database/spc.db')

# 43 lemonparty
# 22 rypaleet
# 1 bar
# 64 777

widthraw_url = os.getenv('spc_widthraw_url', '')

default_settings = {
    'win_basic': 1,
    'win_777': 10,
    'mp_shape': 1,
    'mp_scale': 2,
    'mp_size': 1,
    'max_bet': 1000,
    'mp_10': 0.8,
    'mp_50': 0.5,
    'mp_100': 0.04,
    'mp_1000': 0.001,
    'mp_2000': 0.0001,
    'slot_delay': 5
}


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
        return f'{self.user_id} {self.emoji} ' \
               f'{self.value} {self.bet} ' \
               f'{self.win} {self.datetime}'


class Roll(Model):
    user_id = IntegerField(primary_key=True)
    bet = IntegerField()
    balance = IntegerField()

    class Meta:
        database = db

    def __str__(self):
        return f'{self.user_id} {self.bet} {self.balance}'


class Transaction(Model):
    address = CharField(primary_key=True)
    timestamp = DateTimeField()

    class Meta:
        database = db

    def __str__(self):
        return f'{self.address} {self.timestamp}'


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

        self.settings = default_settings

        self.token = os.getenv('tbot_api')
        self.spc_url = os.getenv('spc_url')
        self.spc_wallet = os.getenv('spc_wallet')
        self.admin_id = int(os.getenv('spc_admin_id', None))

        self._create_tables()

        self.delays = {}
        self.latest_dices = {}
        self.roll_messages = []
        self.secret_key, self.public_key = self._get_keys(self.spc_wallet)
        self.bot = Bot(self.token)
        self.updater = Updater(self.token, use_context=True)

        msg_filter = Filters.text \
                     & (~Filters.forwarded) \
                     & (~Filters.update.edited_message)

        dice_filter = Filters.dice \
                      & (~Filters.forwarded) \
                      & (~Filters.update.edited_message) \
                      & Filters.group

        msg_handler = MessageHandler(filters=msg_filter,
                                     callback=self.message_callback)
        dice_handler = MessageHandler(filters=dice_filter,
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

    def cmd_admin(self, update: Update) -> None:
        global default_settings

        if self.admin_id != update.effective_user.id:
            logger.info(f'user id {update.effective_user.id} is not admin'
                        f' current admin id is {self.admin_id}')
            return
        arguments = update.message.text.split(' ')
        if len(arguments) > 1 and arguments[1] == 'settings':
            if len(arguments) == 2:
                reply_text = 'settings:\n'
                for setting in default_settings:
                    reply_text += f'{setting}: {default_settings[setting]}\n'
                update.message.reply_text(reply_text)
            if len(arguments) > 3:
                setting = arguments[2]
                value = int(arguments[3])
                default_settings[setting] = value
        if len(arguments) > 2 and arguments[1] == 'roll':
            roll_count = int(arguments[2])
            pass

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
            Address.delete() \
                .where(Address.user_id == user.id) \
                .execute()
            username = user.first_name
            if user.last_name:
                username += f' {user.last_name}'
            Address.create(user_id=update.effective_user.id,
                           username=username,
                           address=arguments[1])
            update.message.reply_text('Osoite lisätty!')

    def cmd_widthraw(self, update: Update) -> None:
        arguments = update.message.text.split(' ')

        if not widthraw_url or len(widthraw_url) < 1:
            update.message.reply_text('Kotiuttaminen ei käytössä.')
            return

        if len(arguments) == 1:
            update.message.reply_text('!kotiuta <summa> (min 1000 SPC)')
            return

        try:
            logger.info(f'cmd_widthraw: {update}')
            logger.info(f'cmd_widthraw: arguments {arguments}')
            address = Address.get(Address.user_id == update.effective_user.id)
            logger.info(f'cmd_widthraw: address {address}')
            roll = Roll.get(Roll.user_id == update.effective_user.id)
            logger.info(f'cmd_widthraw: roll {roll}')
            w_value = int(arguments[1])
            logger.info(f'cmd_widthraw: w_value {w_value}')

            if w_value < 1000 or roll.balance < w_value:
                update.message.reply_text('Ei katetta.')
                return

            data_str = sign_data(
                secret_key=self.secret_key,
                data={'to_address': address.address,
                      'from_address': self.public_key,
                      'amount': w_value})

            logger.info(f'cmd_widthraw: data_str {data_str}')
            logger.info(f'cmd_widthraw: widthraw_url {widthraw_url}')

            result = requests.post(
                widthraw_url,
                json={'public_key': self.public_key,
                      'message': data_str},
                headers={'Content-type': 'application/json'})

            if result.status_code == 200:
                roll.balance -= w_value
                roll.save()
                update.message.reply_text(f'Kotiutus {w_value} SPC onnistui.')

        except DoesNotExist:
            update.message.reply_text('Tarkista osoite.')
        except ValueError as e:
            update.message.reply_text('Virheellinen summa.')
        except Exception as e:
            update.message.reply_text('Virhe.')

    def _get_stats_dict(self, win_lose_dict):
        result_dict = {}

        for k, v in win_lose_dict.items():
            try:
                a = Address.get(Address.user_id == k)
                username = a.username
                result_dict[username] = {
                    'rolls': v['rolls'],
                    'wins': v['wins'],
                    'bets': v['bets'],
                    'avgWin': v['wins'] / v['rolls'],
                }
            except:
                pass

        return result_dict

    def cmd_roll_stats(self, update: Update) -> None:
        win_lose_dict = {}

        # 43 lemonparty
        # 22 rypaleet
        # 1 bar
        # 64 777

        counter = 0
        counts = {}

        d: Dice
        for d in Dice.select().where(Dice.emoji == '🎰'):
            user_dict = win_lose_dict.get(d.user_id, {})

            win_lose_dict[d.user_id] = {
                'rolls': user_dict.get('rolls', 0) + 1,
                'wins': user_dict.get('wins', 0) + d.win,
                'bets': user_dict.get('bets', 0) + d.bet
            }

            if d.value in [1, 22, 43, 64]:
                counts[d.value] = counts.get(d.value, 0) + 1
            counter = counter + 1

        stats_dict = self._get_stats_dict(win_lose_dict)

        text_str = 'Stats:\n'
        for k, v in stats_dict.items():
            text_str += f'{k} - ' \
                        f'{v["rolls"]} rolls - ' \
                        f'avgWin {v["avgWin"]:.2f}\n'

        update.message.reply_text(text_str)

    def cmd_roll(self, update: Update) -> None:
        arguments = update.message.text.split(' ')
        user_id = update.effective_user.id

        try:
            roll = self._get_roll(user_id)
            if len(arguments) > 2 and arguments[1] == 'bet':
                bet = int(arguments[2])
                if bet > self.settings['max_bet']:
                    bet = self.settings['max_bet']
                if bet < 0:
                    bet = 0
                roll.bet = bet
                roll.save()
            return_message = (
                '-- Tilisi tiedot -- \n'
                f'Pelitili: {roll.balance:,} SPC\n'
                f'Panos: {roll.bet}\n'
            )
            update.message.reply_text(return_message)
        except Exception as e:
            print(e)
            update.message.reply_text('Osoitetta ei lisätty.')

    @staticmethod
    def get_roll_message(update, new_balance, win_value, win_mp=0, delay=2):
        return {
            'timestamp': arrow.get().shift(seconds=delay).datetime,
            'update': update,
            'win_value': win_value,
            'win_mp': win_mp,
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
            f'!roll bet <summa> -- aseta haluamasi panos (max bet {self.settings["max_bet"]})'
            '\n\n'
            'Elämä on epäreilua ja niin on slotsitkin.\n'
            'Sattuma päättää nyt kertoimen.'
            '\n\n'
            'Jos olet köyhä ja haluat rahat takas, niin:\n'
            '!kotiuta <summa> (min 1000 SPC)\n\n'
            f'Spämmi estää laittamasta liikaa slotteja. '
            f'Pidä vähintään {self.settings["slot_delay"]}s viive.'
        )

    def dice_callback(self, update, context):
        self.handle_dice(update)

    def message_callback(self, update, context):
        logger.info(f'message_callback: {update}')
        args = update.message.text.lower().split(' ')
        if args[0] == '!help':
            update.message.reply_text(self.get_help_text())
        elif args[0] == '!admin':
            self.cmd_admin(update)
        elif args[0] == '!osoite':
            self.cmd_address(update)
        elif args[0] == '!kotiuta':
            self.cmd_widthraw(update)
        elif args[0] == '!roll':
            if len(args) > 1 and args[1] == 'stats':
                self.cmd_roll_stats(update)
            else:
                self.cmd_roll(update)

    def get_win_multiplier(self):
        shape = self.settings['mp_shape']
        scale = self.settings['mp_scale']
        size = self.settings['mp_size']
        win_mp = float(np.random.gamma(shape, scale, size))
        return int(win_mp) + 1

    def handle_dice(self, update):

        if update.message.forward_from is not None:
            return

        logger.info(f'handle_dice: {update}')
        user_id = update.effective_user.id

        now_timestamp = arrow.now().timestamp
        if self.settings['slot_delay'] > 0:
            previous_timestamp = self.delays.get(update.effective_user.id, 0)
            if now_timestamp - previous_timestamp < self.settings['slot_delay']:
                self.bot.delete_message(update.effective_chat.id,
                                        update.effective_message.message_id)
                return
        self.delays[user_id] = now_timestamp

        dice = update.message.dice
        roll = self._get_roll(user_id)

        dice_bet = roll.bet
        win_value = 0

        if '🎰' == dice.emoji and roll.bet > 0:
            if roll.balance >= roll.bet:
                win_value = 0
                win_mp = 0
                if dice.value in [43, 22, 1, 64]:
                    win_mp = self.get_win_multiplier()
                    win_mp = win_mp * self.settings['win_basic']

                    random_float = np.random.random()
                    if dice.value == 64 and random_float <= self.settings['mp_2000']:
                        win_mp *= 2000
                    elif dice.value == 64 and random_float <= self.settings['mp_1000']:
                        win_mp *= 1000
                    elif dice.value == 64 and random_float <= self.settings['mp_100']:
                        win_mp *= 100
                    elif dice.value == 64 and random_float <= self.settings['mp_50']:
                        win_mp *= 50
                    elif dice.value == 64 or random_float <= self.settings['mp_10']:
                        win_mp *= 10

                if win_mp > 0:
                    win_value = round(roll.bet * win_mp, 0)

                new_balance = roll.balance - roll.bet + win_value
                roll.balance = new_balance
                roll.save()

                if win_value > 0:
                    message = self.get_roll_message(update,
                                                    new_balance,
                                                    win_value,
                                                    win_mp=win_mp)
                    self.roll_messages.append(message)

                if new_balance - roll.bet <= 0:
                    update.message.reply_text('Ei enää pelimerkkejä.')

                self.latest_dices[user_id] = Dice.create(
                    user_id=user_id,
                    emoji=dice.emoji,
                    value=dice.value,
                    bet=dice_bet,
                    win=win_value)

        elif '🏀' == dice.emoji and user_id in self.latest_dices:
            last_dice: Dice = self.latest_dices.get(user_id)
            if last_dice.win > 0:
                roll: Roll = self._get_roll(user_id)
                last_win = last_dice.win
                if dice.value > 3:
                    new_win = last_dice.win * 2
                else:
                    new_win = 0

                roll.balance -= last_win
                if new_win > 0:
                    roll.balance += new_win

                roll.save()

                message = self.get_roll_message(update,
                                                roll.balance,
                                                new_win,
                                                delay=4)
                self.roll_messages.append(message)

                last_dice.win = new_win
                last_dice.save()
                self.latest_dices[user_id] = last_dice
            else:
                update.message.reply_text('Ei tuplattavaa.')

    def _get_transactions(self):
        get_chain_address = f"{self.spc_url}/transactions/{self.public_key}"
        response = requests.get(get_chain_address)
        if response.status_code == 200:
            data = json.loads(response.content)
            return sorted(data['transactions'],
                          key=lambda k: k['timestamp'],
                          reverse=False)
        return []

    @staticmethod
    def _get_default_timestamp():
        arw = arrow.utcnow()
        arw = arw.shift(days=-30)
        return arw.datetime

    @staticmethod
    def _update_timestamp(address, timestamp):
        Transaction \
            .insert(address=address, timestamp=timestamp) \
            .on_conflict('replace') \
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
                logger.info(f'handling transaction: {tx}')
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
            message_string = f'-- VOITTO {msg["win_value"]:,} SPC --'
            if msg['win_mp'] > 0:
                message_string += f'\nkerroin: {msg["win_mp"]}'
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
