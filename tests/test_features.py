from unittest.mock import patch
from main import Manager
from test_images import ImageTests as BaseImageTests
from windows_integration import foreground_fullscreen, native_monitors, startup_command

class FeatureTests(BaseImageTests):
    def test_animation_pause_independent(self):
        from PySide6.QtGui import QMovie
        self.c.update_setting('animation_paused', True)
        self.c.update_setting('paused', False)
        self.assertEqual(self.c.movie.state(), QMovie.MovieState.Paused)
        self.c.update_setting('animation_paused', False)
        self.assertEqual(self.c.movie.state(), QMovie.MovieState.Running)

    def test_pin_disconnect_fallback(self):
        self.c.update_setting('monitor','missing')
        self.assertEqual(len(self.c.allowed_rectangles()),1)
        self.c.move(-10000,-10000)
        self.c.recover_position()
        self.assertGreaterEqual(self.c.x(),self.c.allowed_rectangles()[0].x)

    def test_preferences_roundtrip(self):
        with patch('main.config_path',return_value=self.root/'settings.json'):
            m=Manager.__new__(Manager)
            m.quiet_enabled=True
            m.presets={'Evening':[self.c.snapshot()]}
            m.save_preferences()
            m.quiet_enabled=False
            m.presets={}
            m.load_preferences()
            self.assertTrue(m.quiet_enabled)
            self.assertEqual(m.presets['Evening'][0]['png_path'],self.gif)

    def test_quiet_restore(self):
        m=Manager.__new__(Manager)
        m.quiet_enabled=True
        m.quiet_hidden=False
        m.companions={'c':self.c}
        with patch('main.foreground_fullscreen',return_value=True), patch('main.native_monitors',return_value=[]):
            m.check_quiet()
            self.assertFalse(self.c.isVisible())
            m.quiet_enabled=False
            m.check_quiet()
            self.assertTrue(self.c.isVisible())

    def test_windows_probe(self):
        self.assertIsInstance(foreground_fullscreen(native_monitors()),bool)
        self.assertIn('main.py',startup_command())

# The base suite is already discovered from test_images.py.
del BaseImageTests
