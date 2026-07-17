import unittest

from app.modules.shaft.domain.catalog import load_shaft_catalog


class ShaftAwakeningDataTestCase(unittest.TestCase):
    def test_every_catalog_character_has_eight_awakening_descriptions(self) -> None:
        catalog = load_shaft_catalog()
        character_names = {character['name'] for character in catalog['characters']}

        self.assertEqual(character_names, set(catalog['awakenings']))
        self.assertTrue(all(len(entries) == 8 for entries in catalog['awakenings'].values()))

if __name__ == '__main__':
    unittest.main()
