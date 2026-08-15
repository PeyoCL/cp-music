"""
cli.py — Command-line interface for cp-music.

Subcommands
-----------
migrate
    Migrate a playlist from one platform to another.
    Detects an existing destination playlist and only adds missing tracks.

setup-auth
    Generate the ``headers_auth.json`` file required by ytmusicapi from a
    browser-copied cURL command or raw HTTP headers.

Usage examples
--------------
::

    # Spotify → YouTube Music
    python -m cpmusic migrate "123456789" --source spotify --target ytmusic

    # YouTube Music → Spotify  (playlist ID starts with PL)
    python -m cpmusic migrate "PLxxxxxxxxxxxxxxxxxxxxxx" --source ytmusic --target spotify

    # With a custom destination name
    python -m cpmusic migrate "..." --source spotify --target ytmusic --name "My Road Trip"

    # Setup YouTube Music authentication (run once)
    python -m cpmusic setup-auth --from-file curl.txt
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from cpmusic.interfaces import MusicProvider
from cpmusic.migrator import PlaylistMigrator
from cpmusic.providers import SpotifyClient, YTMusicClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return a fully configured :class:`argparse.ArgumentParser`."""

    parser = argparse.ArgumentParser(
        prog="cpmusic",
        description=("cp-music: extensible playlist migration tool."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # ------------------------------------------------------------------
    # migrate
    # ------------------------------------------------------------------
    migrate = subparsers.add_parser(
        "migrate",
        help="Migrate a playlist from one platform to another.",
        description="Fetches tracks from a source platform and adds them to a target platform.",
    )
    migrate.add_argument(
        "playlist_id",
        metavar="PLAYLIST_ID",
        help="The native identifier (ID) of the source playlist.",
    )
    migrate.add_argument(
        "--source",
        required=True,
        choices=["spotify", "ytmusic"],
        help="Source platform identifier.",
    )
    migrate.add_argument(
        "--target",
        required=True,
        choices=["spotify", "ytmusic"],
        help="Target platform identifier.",
    )
    migrate.add_argument(
        "--name",
        metavar="NAME",
        default=None,
        help="Custom name for the destination playlist. Defaults to the source playlist name.",
    )
    migrate.add_argument(
        "--auth-file",
        metavar="PATH",
        default="headers_auth.json",
        help="Path to YouTube Music headers auth JSON (default: headers_auth.json).",
    )
    migrate.add_argument(
        "--sync",
        action="store_true",
        help=(
            "Sync mode: Completely replaces the destination playlist contents to "
            "match the source playlist exactly. WARNING: This will remove any extra "
            "tracks currently in the destination playlist."
        ),
    )
    migrate.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )

    # ------------------------------------------------------------------
    # setup-auth
    # ------------------------------------------------------------------
    setup = subparsers.add_parser(
        "setup-auth",
        help="Generate YouTube Music authentication headers (run once).",
        description=("Converts browser-copied cURL headers into the headers_auth.json file required by ytmusicapi."),
    )
    setup.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default="headers_auth.json",
        help="Output path for the auth JSON file (default: headers_auth.json).",
    )
    setup.add_argument(
        "--from-file",
        "-f",
        metavar="FILE",
        default=None,
        help=(
            "Path to a text file containing raw HTTP headers or a cURL command. If omitted, input is read from stdin."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _configure_logging(verbose: bool) -> None:
    """Configure root logger level and format."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point — called by ``python -m cpmusic`` or the script."""
    load_dotenv()

    parser = _build_parser()
    args = parser.parse_args()

    # ---- setup-auth -------------------------------------------------------
    if args.command == "setup-auth":
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

    # ---- migrate ----------------------------------------------------------
    elif args.command == "migrate":
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
                    "Run 'python -m cpmusic setup-auth' first to authenticate "
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

    # ---- no command -------------------------------------------------------
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
