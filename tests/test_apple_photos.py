from __future__ import annotations

import unittest

from apple_photos_to_immich.apple_photos import as_list, get_bool


class PhotoHelperTests(unittest.TestCase):
    def test_as_list(self) -> None:
        self.assertEqual(as_list(None), [])
        self.assertEqual(as_list("Album"), ["Album"])
        self.assertEqual(as_list(["A", "", "B"]), ["A", "B"])

    def test_get_bool_reads_property_or_method(self) -> None:
        class Photo:
            favorite = True

            def is_movie(self) -> bool:
                return False

        photo = Photo()
        self.assertTrue(get_bool(photo, "favorite"))
        self.assertFalse(get_bool(photo, "is_movie"))


if __name__ == "__main__":
    unittest.main()
