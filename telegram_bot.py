
from telegram import Update
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import Filters
from telegram.ext import CallbackContext

from peewee import SqliteDatabase
from peewee import Model
from peewee import CharField
from peewee import DateTimeField
from peewee import DoubleField
from peewee import IntegerField

from datetime import datetime as dt

from os import environ

# pip install python-telegram-bot
# pip install peewee

db = SqliteDatabase('spc.db')

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
        db.create_tables([Address])

_create_tables()
token = environ['tbot_api']
spc_url = environ['spc_url']
spc_wallet = environ['spc_wallet']

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

updater.start_polling()
updater.idle()
