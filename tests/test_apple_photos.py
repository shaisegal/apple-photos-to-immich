from __future__ import annotations

import unittest

from apple_photos_to_immich.apple_photos import get_album_names


class PhotoStub:
    def __init__(self, *, folder_album=None, albums=None) -> None:
        self.folder_album = folder_album
        self.albums = albums


class ApplePhotosHelpersTests(unittest.TestCase):
    def test_get_album_names_combines_folder_and_plain_album_memberships(self) -> None:
        photo = PhotoStub(
            folder_album=["Trips/Italy", "Family"],
            albums=["Family", "Shared Summer", "_"],
        )

        self.assertEqual(get_album_names(photo), ["Trips/Italy", "Family", "Shared Summer"])

    def test_get_album_names_uses_plain_albums_when_folder_album_missing(self) -> None:
        photo = PhotoStub(folder_album=None, albums=["Shared Album"])

        self.assertEqual(get_album_names(photo), ["Shared Album"])


if __name__ == "__main__":
    unittest.main()
