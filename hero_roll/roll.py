from peewee import DoesNotExist
from telegram import Update
from telegram import User

from .models import Hero

from . import get_settings


def _get_roll_xp(settings: dict, win_value: int) -> int:
    return settings['settings']['roll_xp_win']\
        if win_value > 0 \
           else settings['settings']['roll_xp']

def _get_hero_xp_requirement(hero: Hero, settings: dict) -> int:
    return settings['settings']['base_xp']\
        + (hero.level * settings['settings']['next_xp'])

def _get_hero(user_id) -> Hero:
    try:
        return Hero.get(Hero.user_id == user_id)
    except DoesNotExist:
        return Hero.create(
            user_id=user_id,
            name='',
            level=0,
            xp=0)


def handle_hero_roll(update: Update, win_value: int):
    settings = get_settings()
    user: User = update.effective_user
    hero: Hero = _get_hero(user.id)

    print('hero xp')
    hero.xp = hero.xp + _get_roll_xp(settings, win_value)

    xp_req = _get_hero_xp_requirement(hero, settings)
    if hero.xp >= xp_req:
        hero.level = hero.level + 1
    hero.save()
    print('xp re', xp_req, hero.xp)
