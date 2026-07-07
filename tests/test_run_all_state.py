from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from apple_photos_to_immich.config import Config
from apple_photos_to_immich.commands import run_all


class LoggerStub:
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None

    def error(self, *args, **kwargs) -> None:
        return None


class RunAllStateTests(unittest.TestCase):
    def test_run_all_skips_completed_steps_when_resuming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config(
                immich_server="https://example.com",
                immich_api_key="secret",
                photos_library="/tmp/library.photoslibrary",
                export_dir=root / "export",
                meta_dir=root / "meta",
                album_prefix="Apple Photos",
            )

            import apple_photos_to_immich.commands as commands

            called: list[str] = []

            def make_step(name: str):
                return lambda *args, **kwargs: called.append(name) or 0

            originals = {
                "check": commands.check,
                "export_assets": commands.export_assets,
                "import_assets": commands.import_assets,
                "make_album_map": commands.make_album_map,
                "apply_albums": commands.apply_albums,
                "verify": commands.verify,
            }
            commands.check = make_step("check")
            commands.export_assets = make_step("export")
            commands.import_assets = make_step("import-assets")
            commands.make_album_map = make_step("make-map")
            commands.apply_albums = make_step("apply-albums")
            commands.verify = make_step("verify")
            try:
                exit_code = run_all(config, LoggerStub(), resume=True, reset_state=False)
                self.assertEqual(exit_code, 0)
                self.assertEqual(
                    called,
                    ["check", "export", "import-assets", "make-map", "apply-albums", "verify"],
                )

                called.clear()
                exit_code = run_all(config, LoggerStub(), resume=True, reset_state=False)
                self.assertEqual(exit_code, 0)
                self.assertEqual(called, [])

                state = json.loads(config.state_path.read_text(encoding="utf-8"))
                self.assertIn("verify", state["completedSteps"])
            finally:
                for name, original in originals.items():
                    setattr(commands, name, original)


if __name__ == "__main__":
    unittest.main()
