from peewee import DoesNotExist
from telegram import Update
from telegram import User

from .models import Hero

from . import get_settings


def _get_next_xp_requirement(hero: Hero):
    pass


def _get_hero(user_id) -> Hero:
    try:
        return Hero.get(Hero.user_id == user_id)
    except DoesNotExist:
        return Hero.create(
            user_id=user_id,
            name='',
            level=1,
            xp=0)


def handle_hero_roll(update: Update, win_value: int):
    user: User = update.effective_user
    hero: Hero = _get_hero(user.id)

    print('handle_hero_roll', user, hero, get_settings())
