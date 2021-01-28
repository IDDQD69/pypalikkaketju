
from unittest import TestCase

from hero_roll.roll import _get_new_level
from hero_roll.roll import _get_xp_requirement


class TestHeroRoll(TestCase):

    def test_new_level(self):
        self.assertEqual(1, _get_new_level(1, 0))
        self.assertEqual(2, _get_new_level(1, _get_xp_requirement(1)))
        self.assertEqual(4, _get_new_level(1, _get_xp_requirement(3)))
        self.assertEqual(4, _get_new_level(1, _get_xp_requirement(3) + 10))
