import json
import tempfile
import unittest
from pathlib import Path

from settings import normalize_config, read_config, write_config


class SettingsTests(unittest.TestCase):
    def test_migrates_v01_single_png(self):
        result = normalize_config({'png_path': 'C:/cat.png', 'speed': 90, 'size': 160, 'position': [20, 30]})
        self.assertEqual(len(result['companions']), 1)
        self.assertEqual(result['companions'][0]['mode'], 'Wander')
        self.assertEqual(result['companions'][0]['position'], [20, 30])

    def test_rejects_bad_entries_and_clamps_values(self):
        r = normalize_config({'companions': [None, {}, {'png_path':'x.png', 'speed': -50, 'size': 99999, 'mode':'fake', 'click_through': 'yes', 'position':[1, float('nan')]}]})
        self.assertEqual(len(r['companions']), 1)
        c = r['companions'][0]
        self.assertEqual((c['size'], c['speed'], c['mode']), (512, 10, 'Wander'))
        self.assertFalse(c['click_through'])
        self.assertIsNone(c['position'])

    def test_saved_and_read_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'some' / 'settings.json'
            value = {'companions': [{'png_path':'C:/avatar.png', 'size':180}]}
            write_config(p, value)
            c = read_config(p)
            self.assertEqual(c['companions'][0]['size'],180)
            self.assertFalse(p.with_suffix('.json.tmp').exists())

    def test_bad_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'settings.json'
            p.write_text('bad JSON', encoding='utf-8')
            self.assertEqual(read_config(p), {'companions': []})

    def test_duplicate_ids_replaced(self):
        r = normalize_config({'companions': [{'id':'same','png_path':'1.png'}, {'id':'same','png_path':'2.png'}]})
        self.assertNotEqual(r['companions'][0]['id'],r['companions'][1]['id'])


if __name__ == '__main__':
    unittest.main()
