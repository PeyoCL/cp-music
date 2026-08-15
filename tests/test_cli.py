"""
test_cli.py — Unit tests for playlist-migrate command-line interface.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from playlist_migrate.cli import _build_parser, _build_setup_auth_parser, main


class TestCLIParser:
    def test_direct_migration_arguments(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["PL_12345", "--source", "spotify", "--target", "ytmusic", "--name", "My List"])

        assert args.playlist_id == "PL_12345"
        assert args.source == "spotify"
        assert args.target == "ytmusic"
        assert args.name == "My List"
        assert args.sync is False

    def test_short_flags_migration_arguments(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["PL_12345", "-s", "ytmusic", "-t", "spotify", "--sync", "-v"])

        assert args.playlist_id == "PL_12345"
        assert args.source == "ytmusic"
        assert args.target == "spotify"
        assert args.sync is True
        assert args.verbose is True

    def test_setup_auth_parser(self) -> None:
        parser = _build_setup_auth_parser()
        args = parser.parse_args(["--from-file", "curl.txt", "--output", "custom_auth.json"])

        assert args.from_file == "curl.txt"
        assert args.output == "custom_auth.json"


class TestCLIExecution:
    def test_missing_arguments_exits_with_error(self) -> None:
        with patch("sys.argv", ["playlist-migrate"]), pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_same_source_and_target_exits_with_error(self) -> None:
        with (
            patch("sys.argv", ["playlist-migrate", "PL_123", "--source", "spotify", "--target", "spotify"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 1

    def test_setup_auth_execution_with_file(self, tmp_path) -> None:
        curl_file = tmp_path / "curl.txt"
        curl_file.write_text("cookie: session=123", encoding="utf-8")

        with (
            patch("sys.argv", ["playlist-migrate", "setup-auth", "--from-file", str(curl_file)]),
            patch("playlist_migrate.cli.YTMusicClient.setup_headers_auth") as mock_setup_auth,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0
        mock_setup_auth.assert_called_once_with(output_filepath="headers_auth.json", raw_input="cookie: session=123")

    def test_direct_migration_success(self) -> None:
        mock_migrator = MagicMock()
        mock_migrator.migrate = AsyncMock()

        with (
            patch("sys.argv", ["playlist-migrate", "37i9dQZF1DXcBWIGoYBM5M", "-s", "spotify", "-t", "ytmusic"]),
            patch("playlist_migrate.cli.SpotifyClient", return_value=MagicMock()),
            patch("playlist_migrate.cli.YTMusicClient", return_value=MagicMock()),
            patch("playlist_migrate.cli.Path.exists", return_value=True),
            patch("playlist_migrate.cli.PlaylistMigrator", return_value=mock_migrator),
        ):
            main()

            mock_migrator.migrate.assert_awaited_once_with(
                source_id="spotify",
                target_id="ytmusic",
                playlist_identifier="37i9dQZF1DXcBWIGoYBM5M",
                target_name=None,
                sync=False,
            )

    def test_backward_compatible_migrate_alias(self) -> None:
        mock_migrator = MagicMock()
        mock_migrator.migrate = AsyncMock()

        with (
            patch("sys.argv", ["playlist-migrate", "migrate", "PL_123", "-s", "ytmusic", "-t", "spotify"]),
            patch("playlist_migrate.cli.SpotifyClient", return_value=MagicMock()),
            patch("playlist_migrate.cli.YTMusicClient", return_value=MagicMock()),
            patch("playlist_migrate.cli.Path.exists", return_value=True),
            patch("playlist_migrate.cli.PlaylistMigrator", return_value=mock_migrator),
        ):
            main()

            mock_migrator.migrate.assert_awaited_once_with(
                source_id="ytmusic",
                target_id="spotify",
                playlist_identifier="PL_123",
                target_name=None,
                sync=False,
            )
