import unittest

from motion import Rect, bounced_step, closest_visible, fully_visible


class GeometryTests(unittest.TestCase):
    def test_inside_one_monitor(self):
        self.assertTrue(fully_visible(20, 30, 100, 100, [Rect(0, 0, 1920, 1080)]))
        self.assertFalse(fully_visible(-30, 0, 100, 100, [Rect(0, 0, 1920, 1080)]))

    def test_crossing_touching_monitors(self):
        screens = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1920, 1080)]
        self.assertTrue(fully_visible(1880, 120, 160, 160, screens))

    def test_gap_between_monitors(self):
        screens = [Rect(0, 0, 1920, 1080), Rect(1930, 0, 1920, 1080)]
        self.assertFalse(fully_visible(1890, 120, 160, 160, screens))

    def test_misaligned_monitors(self):
        screens = [Rect(0, 0, 1920, 1080), Rect(1920, 700, 1920, 1080)]
        self.assertTrue(fully_visible(1880, 750, 160, 160, screens))
        self.assertFalse(fully_visible(1880, 600, 160, 160, screens))

    def test_nearest_screen_location(self):
        self.assertEqual(closest_visible(-150, -5, 100, 100, [Rect(0, 0, 1920, 1080)]), (0, 0))
        self.assertEqual(closest_visible(2000, 2000, 100, 100, [Rect(0, 0, 1920, 1080)]), (1820, 980))

    def test_bouncing_off_right_edge(self):
        x, y, dx, dy = bounced_step(1870, 100, 1, 0, 90, 0.1, 50, 50, [Rect(0, 0, 1920, 1080)])
        self.assertEqual(dx, -1)
        self.assertEqual(dy, 0)
        self.assertEqual((x, y), (1861, 100))

    def test_bouncing_is_dt_independent_of_frame_rate(self):
        screens = [Rect(0, 0, 400, 400)]
        x, y, dx, dy = bounced_step(100, 100, 1, 0, 90, 0.02, 50, 50, screens)
        self.assertAlmostEqual(x, 101.8)
        self.assertTrue(fully_visible(x, y, 50, 50, screens))


if __name__ == '__main__':
    unittest.main()
