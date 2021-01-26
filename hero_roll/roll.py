from peewee import DoesNotExist
from telegram import Update
from telegram import User

from .models import Hero

from . import get_settings


def _get_roll_xp(settings: dict, win_value: int) -> int:
    return win_value * settings['settings']['roll_xp_win']\
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


def _handle_hero_level(settings, hero):
    fail_counter = 0
    xp_req = _get_hero_xp_requirement(hero, settings)
    while hero.xp >= xp_req:
        hero.level = hero.level + 1
        xp_req = _get_hero_xp_requirement(hero, settings)
        fail_counter = fail_counter + 1
        if fail_counter < 300:
            break


def handle_hero_roll(update: Update, win_value: int):
    settings = get_settings()
    user: User = update.effective_user
    hero: Hero = _get_hero(user.id)

    hero.xp = hero.xp + _get_roll_xp(settings, win_value)

    _handle_hero_level(settings, hero)
    hero.save()
    xp_req = _get_hero_xp_requirement(hero, settings)
    print('xp re', xp_req, hero.xp, hero.level)


def get_hero_info(update: Update):
    settings = get_settings()
    user: User = update.effective_user
    hero: Hero = _get_hero(user.id)
    return {
        'hero_level': hero.level,
        'hero_xp': hero.xp,
        'hero_req_xp': _get_hero_xp_requirement(hero, settings)
    }