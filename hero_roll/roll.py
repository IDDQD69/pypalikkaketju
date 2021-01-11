
from telegram import Update
from telegram import User

from .models import Hero

from . import get_settings


def _get_next_xp_requirement(hero: Hero):
    pass


def handle_hero_roll(update: Update, win_value: int):
    user: User = update.effective_user
    hero: Hero = Hero.get(user_id=user.id)
    print('handle_hero_roll', user, hero)
