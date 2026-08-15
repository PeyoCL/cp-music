"""
cli.py — Command-line interface for playlist-migrate.

Direct Migration:
    playlist-migrate "PLAYLIST_ID" --source spotify --target ytmusic
    playlist-migrate "PLxxxxxxxxxxxxxxxxxxxxxx" --source ytmusic --target spotify
    playlist-migrate "..." --source spotify --target ytmusic --name "My Road Trip"

Authentication Setup:
    playlist-migrate setup-auth --from-file curl.txt
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from playlist_migrate.interfaces import MusicProvider
from playlist_migrate.migrator import PlaylistMigrator
from playlist_migrate.providers import SpotifyClient, YTMusicClient

logger = logging.getLogger(__name__)


def _add_migration_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "playlist_id",
        nargs="?",
        metavar="PLAYLIST_ID",
        help="The native identifier (ID) of the source playlist.",
    )
    p.add_argument(
        "--source",
        "-s",
        choices=["spotify", "ytmusic"],
        help="Source platform identifier.",
    )
    p.add_argument(
        "--target",
        "-t",
        choices=["spotify", "ytmusic"],
        help="Target platform identifier.",
    )
    p.add_argument(
        "--name",
        "-n",
        metavar="NAME",
        default=None,
        help="Custom name for destination playlist (defaults to source playlist name).",
    )
    p.add_argument(
        "--auth-file",
        metavar="PATH",
        default="headers_auth.json",
        help="Path to YouTube Music headers auth JSON (default: headers_auth.json).",
    )
    p.add_argument(
        "--sync",
        action="store_true",
        help="Sync mode: Replaces destination playlist contents to match source exactly.",
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )


def _build_parser() -> argparse.ArgumentParser:
    """Return the migration argument parser."""
    parser = argparse.ArgumentParser(
        prog="playlist-migrate",
        description="playlist-migrate: Extensible playlist migration between streaming services.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Commands & Examples:
  playlist-migrate <PLAYLIST_ID> --source <SRC> --target <TGT>   Migrate a playlist directly
  playlist-migrate setup-auth [--from-file FILE]                 Generate YTMusic auth headers
""",
    )
    _add_migration_arguments(parser)
    return parser


def _build_setup_auth_parser() -> argparse.ArgumentParser:
    """Return the setup-auth argument parser."""
    parser = argparse.ArgumentParser(
        prog="playlist-migrate setup-auth",
        description="Converts browser-copied cURL headers into headers_auth.json for ytmusicapi.",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default="headers_auth.json",
        help="Output path for the auth JSON file (default: headers_auth.json).",
    )
    parser.add_argument(
        "--from-file",
        "-f",
        metavar="FILE",
        default=None,
        help="Path to text file containing raw HTTP headers or cURL command. If omitted, read from stdin.",
    )
    return parser


def _configure_logging(verbose: bool) -> None:
    """Configure root logger level and format."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(args_list: list[str] | None = None) -> None:
    """CLI entry point — called by ``python -m playlist_migrate`` or ``playlist-migrate``."""
    load_dotenv()
    raw_args = sys.argv[1:] if args_list is None else args_list

    # ---- setup-auth -------------------------------------------------------
    if raw_args and raw_args[0] == "setup-auth":
        parser = _build_setup_auth_parser()
        args = parser.parse_args(raw_args[1:])
        _configure_logging(verbose=False)
        raw_text: str | None = None
        if args.from_file:
            input_path = Path(args.from_file)
            if not input_path.exists():
                print(f"❌ Error: File '{args.from_file}' not found.")
                sys.exit(1)
            raw_text = input_path.read_text(encoding="utf-8")

        YTMusicClient.setup_headers_auth(output_filepath=args.output, raw_input=raw_text)
        sys.exit(0)

    parser = _build_parser()
    args = parser.parse_args(raw_args)

    # ---- direct migration -------------------------------------------------
    if not args.playlist_id or not args.source or not args.target:
        parser.print_help()
        sys.exit(1)

    _configure_logging(verbose=args.verbose)

    if args.source == args.target:
        print("❌ Error: --source and --target cannot be the same platform.")
        sys.exit(1)

    providers: dict[str, MusicProvider] = {}

    # Initialize only required clients
    if "spotify" in (args.source, args.target):
        providers["spotify"] = SpotifyClient()

    if "ytmusic" in (args.source, args.target):
        auth_file = Path(args.auth_file)
        if not auth_file.exists():
            print(
                f"⚠️  Auth file '{args.auth_file}' not found.\n"
                "Run 'playlist-migrate setup-auth' first to authenticate "
                "your YouTube Music account."
            )
            sys.exit(1)
        providers["ytmusic"] = YTMusicClient(auth_filepath=args.auth_file)

    migrator = PlaylistMigrator(providers)

    try:
        asyncio.run(
            migrator.migrate(
                source_id=args.source,
                target_id=args.target,
                playlist_identifier=args.playlist_id,
                target_name=args.name,
                sync=args.sync,
            )
        )
    except Exception as err:
        logger.error("Migration failed: %s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
