from peewee import DoesNotExist
from telegram import Update
from telegram import User

from .models import Hero


def _get_roll_xp(win_value: int) -> int:
    return win_value * 0.01 if win_value > 0 else 5


def _get_hero_xp_requirement(hero: Hero) -> int:
    return 100 + (hero.level * 200)


def _get_hero(user_id) -> Hero:
    try:
        return Hero.get(Hero.user_id == user_id)
    except DoesNotExist:
        return Hero.create(
            user_id=user_id,
            name='',
            level=0,
            xp=0)


def _handle_hero_level(hero):
    fail_counter = 0
    xp_req = _get_hero_xp_requirement(hero)
    while hero.xp >= xp_req:
        hero.level = hero.level + 1
        xp_req = _get_hero_xp_requirement(hero)
        fail_counter = fail_counter + 1
        if fail_counter < 300:
            break


def handle_hero_roll(update: Update, win_value: int):
    user: User = update.effective_user
    hero: Hero = _get_hero(user.id)

    hero.xp = hero.xp + _get_roll_xp(win_value)

    _handle_hero_level(hero)
    hero.save()


def get_hero_info(update: Update):
    user: User = update.effective_user
    hero: Hero = _get_hero(user.id)
    return {
        'hero_level': hero.level,
        'hero_xp': hero.xp,
        'hero_req_xp': _get_hero_xp_requirement(hero)
    }