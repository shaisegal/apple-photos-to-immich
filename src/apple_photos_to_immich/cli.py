from __future__ import annotations

import argparse
import sys

from .commands import (
    apply_albums,
    check,
    export_assets,
    import_assets,
    make_album_map,
    run_all,
    verify,
    wait_for_immich,
)
from .config import find_config_file, load_config
from .logging_utils import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apple-photos-to-immich")
    parser.add_argument("--config", help="Path to config.toml")
    parser.add_argument("--debug-json", action="store_true", help="Write JSON debug log")
    parser.add_argument("--verbose", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--test", action="store_true")
    export_parser.add_argument("--dry-run", action="store_true")
    export_parser.add_argument("--update", action="store_true")

    import_parser = subparsers.add_parser("import-assets")
    import_parser.add_argument("--dry-run", action="store_true")
    import_parser.add_argument("--no-wait", action="store_true")
    import_parser.add_argument("--wait-timeout", type=float, default=1800.0)
    import_parser.add_argument("--wait-interval", type=float, default=10.0)

    subparsers.add_parser("make-map")

    wait_parser = subparsers.add_parser("wait-for-immich")
    wait_parser.add_argument("--timeout", type=float, default=1800.0)
    wait_parser.add_argument("--interval", type=float, default=10.0)

    apply_parser = subparsers.add_parser("apply-albums")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.add_argument("--sleep", type=float, default=0.1)

    subparsers.add_parser("verify")

    all_parser = subparsers.add_parser("all")
    all_parser.add_argument("--dry-run", action="store_true")
    all_parser.add_argument("--test", action="store_true")
    all_parser.add_argument("--no-resume", action="store_true")
    all_parser.add_argument("--reset-state", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config_path = find_config_file(args.config)
    config = load_config(config_path)
    logger = setup_logging(config.log_dir, debug_json=args.debug_json, verbose=args.verbose)

    try:
        if args.command == "check":
            return check(config, logger)
        if args.command == "export":
            return export_assets(
                config,
                logger,
                test_mode=args.test,
                dry_run=args.dry_run,
                update=args.update,
            )
        if args.command == "import-assets":
            exit_code = import_assets(config, logger, dry_run=args.dry_run)
            if exit_code != 0 or args.dry_run:
                return exit_code
            if not args.no_wait:
                exit_code = wait_for_immich(
                    config,
                    logger,
                    timeout_seconds=args.wait_timeout,
                    interval_seconds=args.wait_interval,
                )
                if exit_code != 0:
                    return exit_code
            return 0
        if args.command == "make-map":
            return make_album_map(config, logger)
        if args.command == "wait-for-immich":
            return wait_for_immich(
                config,
                logger,
                timeout_seconds=args.timeout,
                interval_seconds=args.interval,
            )
        if args.command == "apply-albums":
            return apply_albums(config, logger, dry_run=args.dry_run, sleep_seconds=args.sleep)
        if args.command == "verify":
            return verify(config, logger)
        if args.command == "all":
            return run_all(
                config,
                logger,
                dry_run=args.dry_run,
                test_mode=args.test,
                resume=not args.no_resume,
                reset_state=args.reset_state,
            )
    except (RuntimeError, ModuleNotFoundError, FileNotFoundError, ValueError) as exc:
        logger.error(str(exc))
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
