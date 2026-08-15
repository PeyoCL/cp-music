"""
test_migrator.py — Unit tests for playlist-migrate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from playlist_migrate.exceptions import NetworkError, RateLimitError
from playlist_migrate.migrator import PlaylistMigrator
from playlist_migrate.models import (
    MigrationResult,
    Playlist,
    SpotifyPlaylist,
    Track,
)
from playlist_migrate.providers import SpotifyClient, YTMusicClient

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_track(
    title: str = "Song",
    artist: str = "Artist",
    isrc: str | None = None,
    video_id: str | None = None,
    spotify_id: str | None = None,
) -> Track:
    return Track(
        title=title,
        artists=[artist],
        album="Album",
        duration_ms=200_000,
        isrc=isrc,
        video_id=video_id,
        spotify_id=spotify_id,
    )


def make_playlist(
    name: str = "My Playlist",
    tracks: list[Track] | None = None,
    source: str = "Spotify",
) -> Playlist:
    return Playlist(
        id="pl_001",
        name=name,
        description="Test playlist",
        source=source,
        tracks=tracks or [],
    )


# ---------------------------------------------------------------------------
# Track tests
# ---------------------------------------------------------------------------


class TestTrack:
    def test_artist_name_single(self) -> None:
        t = make_track(artist="Queen")
        assert t.artist_name == "Queen"

    def test_artist_name_multiple(self) -> None:
        t = Track(
            title="Song",
            artists=["Artist A", "Artist B"],
            album="Album",
            duration_ms=0,
        )
        assert t.artist_name == "Artist A, Artist B"

    def test_search_query(self) -> None:
        t = make_track(title="Bohemian Rhapsody", artist="Queen")
        assert t.search_query == "Queen - Bohemian Rhapsody"

    def test_display_name(self) -> None:
        t = make_track(title="Bohemian Rhapsody", artist="Queen")
        assert t.display_name == "Queen — Bohemian Rhapsody"

    def test_search_query_no_artists(self) -> None:
        t = Track(title="Unknown", artists=[], album="", duration_ms=0)
        assert t.search_query == "Unknown"


# ---------------------------------------------------------------------------
# SpotifyPlaylist alias
# ---------------------------------------------------------------------------


class TestSpotifyPlaylistAlias:
    def test_alias_is_playlist(self) -> None:
        """SpotifyPlaylist must still be usable as a Playlist alias."""
        pl = SpotifyPlaylist(
            id="abc",
            name="Legacy",
            description="",
            source="Spotify",
        )
        assert isinstance(pl, Playlist)


# ---------------------------------------------------------------------------
# SpotifyClient static helpers
# ---------------------------------------------------------------------------


class TestSpotifyClientHelpers:
    def test_extract_playlist_id_from_url(self) -> None:
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc"
        assert SpotifyClient.extract_playlist_id(url) == "37i9dQZF1DXcBWIGoYBM5M"

    def test_extract_playlist_id_raw(self) -> None:
        raw = "37i9dQZF1DXcBWIGoYBM5M"
        assert SpotifyClient.extract_playlist_id(raw) == raw


# ---------------------------------------------------------------------------
# MigrationResult
# ---------------------------------------------------------------------------


class TestMigrationResult:
    def test_success_rate_with_skips(self) -> None:
        result = MigrationResult(
            playlist_name="Test",
            target_playlist_id="PL001",
            direction="Spotify → YouTube Music",
            total_tracks=10,
            migrated_count=6,
            skipped_count=2,
        )
        # 6 added + 2 skipped = 8 / 10 = 80 %
        assert result.success_rate == pytest.approx(80.0)

    def test_success_rate_zero_total(self) -> None:
        result = MigrationResult(
            playlist_name="Empty",
            target_playlist_id="",
            direction="YouTube Music → Spotify",
            total_tracks=0,
            migrated_count=0,
        )
        assert result.success_rate == 0.0


# ---------------------------------------------------------------------------
# YTMusicClient header parsing
# ---------------------------------------------------------------------------


class TestYTMusicClientHeaders:
    def test_parse_curl_headers(self) -> None:
        curl_text = (
            "curl 'https://music.youtube.com/youtubei/v1/browse?key=123' \\\n"
            "  -H 'cookie: VISITOR_INFO1_LIVE=xyz;' \\\n"
            "  -H 'x-goog-authuser: 0'\n"
        )
        headers = YTMusicClient.parse_raw_or_curl_headers(curl_text)
        assert headers.get("cookie") == "VISITOR_INFO1_LIVE=xyz;"
        assert headers.get("x-goog-authuser") == "0"

    def test_parse_raw_headers(self) -> None:
        raw = "cookie: session=abc\nx-goog-authuser: 1\n"
        headers = YTMusicClient.parse_raw_or_curl_headers(raw)
        assert headers.get("cookie") == "session=abc"
        assert headers.get("x-goog-authuser") == "1"


# ---------------------------------------------------------------------------
# PlaylistMigrator — Generic tests
# ---------------------------------------------------------------------------


class TestMigratorGeneric:
    """Tests for generic migrate with mocked clients."""

    def _make_migrator(self, mock_sp: MagicMock, mock_yt: MagicMock) -> PlaylistMigrator:
        return PlaylistMigrator(providers={"spotify": mock_sp, "ytmusic": mock_yt})

    @pytest.mark.asyncio
    async def test_new_playlist_created_and_tracks_added(self, mock_sp: MagicMock, mock_yt: MagicMock) -> None:
        tracks = [
            make_track("Song A", isrc="ISRC001"),
            make_track("Song B"),
        ]
        source_pl = make_playlist(name="My Spotify PL", tracks=tracks)

        mock_sp.get_playlist.return_value = source_pl

        mock_yt.search_track.side_effect = ["vid001", "vid002"]
        mock_yt.get_existing_playlist.return_value = None  # no existing playlist
        mock_yt.create_playlist.return_value = "PL_NEW"

        migrator = self._make_migrator(mock_sp, mock_yt)
        result = await migrator.migrate(source_id="spotify", target_id="ytmusic", playlist_identifier="abc")

        assert result.direction == "Spotify → Ytmusic"
        assert result.target_playlist_id == "PL_NEW"
        assert result.migrated_count == 2
        assert result.skipped_count == 0
        mock_yt.add_tracks.assert_called_once_with(playlist_id="PL_NEW", track_ids=["vid001", "vid002"])

    @pytest.mark.asyncio
    async def test_existing_playlist_skips_duplicates(self, mock_sp: MagicMock, mock_yt: MagicMock) -> None:
        tracks = [
            make_track("Song A"),
            make_track("Song B"),
        ]
        source_pl = make_playlist(name="Road Trip", tracks=tracks)

        # Existing playlist has Song A already (mock its video_id)
        existing_track = make_track("Song A", video_id="vid001")
        existing_pl = make_playlist(name="Road Trip", source="YouTube Music", tracks=[existing_track])
        existing_pl.id = "PL_EXISTING"

        mock_sp.get_playlist.return_value = source_pl

        mock_yt.search_track.side_effect = ["vid001", "vid002"]
        mock_yt.get_existing_playlist.return_value = existing_pl

        migrator = self._make_migrator(mock_sp, mock_yt)
        result = await migrator.migrate(source_id="spotify", target_id="ytmusic", playlist_identifier="abc")

        assert result.migrated_count == 1
        assert result.skipped_count == 1
        mock_yt.add_tracks.assert_called_once_with(playlist_id="PL_EXISTING", track_ids=["vid002"])

    @pytest.mark.asyncio
    async def test_empty_source_playlist_returns_zero_result(self, mock_sp: MagicMock, mock_yt: MagicMock) -> None:
        empty_pl = make_playlist(name="Empty", tracks=[])
        mock_sp.get_playlist.return_value = empty_pl

        migrator = self._make_migrator(mock_sp, mock_yt)
        result = await migrator.migrate(source_id="spotify", target_id="ytmusic", playlist_identifier="url")

        assert result.total_tracks == 0
        assert result.migrated_count == 0
        mock_yt.create_playlist.assert_not_called()

    @pytest.mark.asyncio
    async def test_ytmusic_to_spotify_skips_duplicates(self, mock_sp: MagicMock, mock_yt: MagicMock) -> None:
        tracks = [
            make_track("Song X", spotify_id="aaa"),
            make_track("Song Y", spotify_id="bbb"),
        ]
        source_pl = make_playlist(name="Chill Vibes", tracks=tracks, source="YouTube Music")

        existing_track = make_track("Song X", spotify_id="aaa")
        existing_sp_pl = Playlist(
            id="sp_existing",
            name="Chill Vibes",
            description="",
            source="Spotify",
            tracks=[existing_track],
        )

        mock_yt.get_playlist.return_value = source_pl

        mock_sp.search_track.side_effect = [
            "spotify:track:aaa",
            "spotify:track:bbb",
        ]
        mock_sp.get_existing_playlist.return_value = existing_sp_pl

        migrator = self._make_migrator(mock_sp, mock_yt)
        result = await migrator.migrate(source_id="ytmusic", target_id="spotify", playlist_identifier="PL_SOURCE")

        assert result.migrated_count == 1
        assert result.skipped_count == 1
        # Only bbb should be added
        mock_sp.add_tracks.assert_called_once_with(
            playlist_id="sp_existing",
            track_ids=["spotify:track:bbb"],
        )


class TestRateLimitingAndExceptions:
    """Tests for rate limiting and exceptions."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exception_type", [RateLimitError, NetworkError])
    async def test_retry_on_exception(self, mock_sp: MagicMock, mock_yt: MagicMock, exception_type: Exception) -> None:
        """Test that the migrator gracefully retries and eventually fails on repeated exceptions."""
        tracks = [make_track("Song X")]
        source_pl = make_playlist(name="My Spotify PL", tracks=tracks)
        mock_sp.get_playlist.return_value = source_pl

        # We need search_track to throw the exception
        mock_yt.search_track.side_effect = exception_type("Test error")
        mock_yt.get_existing_playlist.return_value = None
        mock_yt.create_playlist.return_value = "PL_NEW"

        migrator = PlaylistMigrator(providers={"spotify": mock_sp, "ytmusic": mock_yt})

        result = await migrator.migrate(source_id="spotify", target_id="ytmusic", playlist_identifier="abc")

        # It should report as failed
        assert len(result.failed_tracks) == 1
        assert result.migrated_count == 0
        assert mock_yt.search_track.call_count == 3
