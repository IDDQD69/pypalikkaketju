from peewee import DoesNotExist
from telegram import Update
from telegram import User

from .models import Hero


def _get_roll_xp(win_value: int) -> int:
    return win_value * 0.1 + 10 if win_value > 0 else 0


def _get_xp_requirement(level: int) -> int:
    return 100 + ((level * 200) * level)


def _get_hero(user_id) -> Hero:
    try:
        return Hero.get(Hero.user_id == user_id)
    except DoesNotExist:
        return Hero.create(
            user_id=user_id,
            name='',
            level=0,
            xp=0)


def _get_new_level(current_level, new_xp):
    return current_level \
        if _get_xp_requirement(current_level) > new_xp \
        else _get_new_level(current_level + 1, new_xp)


def handle_hero_roll(update: Update, win_value: int) -> bool:
    user: User = update.effective_user
    hero: Hero = _get_hero(user.id)

    old_level = hero.level
    hero.xp = hero.xp + _get_roll_xp(win_value)
    hero.level = _get_new_level(hero.level, hero.xp)
    hero.save()
    return old_level < hero.level


def get_hero_info(update: Update):
    user: User = update.effective_user
    hero: Hero = _get_hero(user.id)
    return {
        'hero_level': hero.level,
        'hero_xp': hero.xp,
        'hero_req_xp': _get_xp_requirement(hero.level)
    }