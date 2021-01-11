from peewee import SqliteDatabase, IntegerField, \
    CharField, DateTimeField, Model, ForeignKeyField
import datetime

db = SqliteDatabase('database/hero.db')


class Hero(Model):
    user_id = IntegerField()
    name = CharField()
    level = IntegerField()
    xp = IntegerField()

    class Meta:
        database = db


class HeroEquipment(Model):
    user_id = IntegerField()
    hero = ForeignKeyField(Hero, backref='equipment')
    name = CharField()
    effects = CharField()
    bet = IntegerField()
    win = IntegerField()
    drop_datetime = DateTimeField(default=datetime.datetime.now)
    equip_datetime = DateTimeField(null=True)

    class Meta:
        database = db


class EquipmentEffect(Model):
    equipment = ForeignKeyField(HeroEquipment, backref='effects')
    effect = CharField()
    value = IntegerField()

    class Meta:
        database = db


def create_tables():
    db.create_tables([Hero,
                      HeroEquipment,
                      EquipmentEffect])