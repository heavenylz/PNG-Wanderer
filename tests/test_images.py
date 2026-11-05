import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QMovie
from PySide6.QtTest import QTest
from main import Companion, image_ok
from settings import normalize_companion, write_config, read_config

class StubManager:
    tray_available = False
    def queue_save(self): pass
    def refresh_settings(self): pass

class ImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Generated fixture includes transparency and unequal frame durations.
        from PIL import Image
        frames = []
        for color in ('red', 'blue'):
            im = Image.new('RGBA', (32, 16))
            for x in range(4, 28):
                for y in range(4, 12): im.putpixel((x,y), color == 'red' and (255,0,0,255) or (0,0,255,255))
            frames.append(im)
        self.gif = str(self.root / 'pet.GIF')
        self.png = str(self.root / 'pet.png')
        frames[0].save(self.gif, save_all=True, append_images=frames[1:], duration=[80,160], loop=0, disposal=2)
        frames[0].save(self.png)
        self.c = Companion(StubManager(), normalize_companion({'png_path':self.gif, 'paused':True}))

    def tearDown(self):
        self.c.close()
        self.app.processEvents()
        self.tmp.cleanup()

    def test_frames_advance_while_movement_paused(self):
        seen = []
        self.c.movie.frameChanged.connect(seen.append)
        pos = self.c.pos()
        QTest.qWait(420)
        self.assertIn(1, seen)
        self.assertIn(0, seen)
        self.assertEqual(self.c.pos(), pos)
        self.assertEqual(self.c.movie.speed(),100)
        self.assertEqual(self.c.movie.loopCount(),-1)
        self.assertEqual(self.c.picture.toImage().pixelColor(0,0).alpha(),0)

    def test_resize_and_replace(self):
        self.c.update_setting('size',240)
        self.assertEqual((self.c.width(),self.c.height()),(240,120))
        self.c.movie.jumpToFrame(1)
        self.assertEqual(self.c.width(),240)
        self.c.change_image(self.png)
        self.assertIsNone(self.c.movie)
        self.assertFalse(self.c.picture.isNull())
        self.c.change_image(self.gif)
        self.assertIsNotNone(self.c.movie)
        self.c.change_image(str(self.root/'missing.gif'))
        self.assertEqual(self.c.data['png_path'], self.gif)
        self.c.close()
        self.assertIsNone(self.c.movie)
        self.assertFalse(self.c.timer.isActive())

    def test_validation_and_persistence(self):
        self.assertTrue(image_ok(self.gif))
        self.assertTrue(image_ok(self.png))
        bad = self.root/'bad.gif'
        bad.write_bytes(b'not an image')
        self.assertFalse(image_ok(str(bad)))
        self.assertFalse(image_ok(str(self.root/'missing.png')))
        p = self.root/'settings.json'
        write_config(p, {'companions':[self.c.snapshot()]})
        self.assertEqual(read_config(p)['companions'][0]['png_path'],self.gif)

    def test_all_modes_move_with_animation(self):
        from motion import Rect
        from PySide6.QtCore import QPoint
        import time
        self.c.update_setting('paused',False)
        with patch('main.display_rectangles',return_value=[Rect(-1000,-1000,4000,4000)]), patch('main.QCursor.pos',return_value=QPoint(1500,1500)):
            for mode in ('Wander','Bounce','Follow cursor'):
                self.c.update_setting('mode',mode)
                self.c.move(0,0)
                self.c.sync_coordinates()
                self.c.last_time = time.monotonic()-0.05
                self.c.tick()
                self.assertNotEqual((self.c.xf,self.c.yf),(0,0))
                self.assertEqual(self.c.movie.state(),QMovie.MovieState.Running)
