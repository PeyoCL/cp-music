"""
test_ytmusic_provider.py — Unit tests with mocks for YTMusicClient provider.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from playlist_migrate.exceptions import LikedSongsFetchError, PlaylistFetchError, YTMusicAuthError
from playlist_migrate.models import Track
from playlist_migrate.providers.ytmusic import YTMusicClient


@pytest.fixture
def ytmusic_client_mocked() -> tuple[YTMusicClient, MagicMock]:
    """Creates a YTMusicClient instance with mocked ytmusicapi.YTMusic instance."""
    mock_yt = MagicMock()
    with (
        patch("playlist_migrate.providers.ytmusic.Path.exists", return_value=True),
        patch("playlist_migrate.providers.ytmusic.YTMusic", return_value=mock_yt),
    ):
        client = YTMusicClient(auth_filepath="dummy_headers.json")
        client.ytmusic = mock_yt
        return client, mock_yt


class TestYTMusicInitialization:
    def test_init_with_existing_auth_file(self) -> None:
        with (
            patch("playlist_migrate.providers.ytmusic.Path.exists", return_value=True),
            patch("playlist_migrate.providers.ytmusic.YTMusic") as mock_yt_cls,
        ):
            client = YTMusicClient(auth_filepath="headers_auth.json")
            mock_yt_cls.assert_called_once_with("headers_auth.json")
            assert client.ytmusic is not None

    def test_init_without_auth_file_fallback_to_read_only(self) -> None:
        with (
            patch("playlist_migrate.providers.ytmusic.Path.exists", return_value=False),
            patch("playlist_migrate.providers.ytmusic.YTMusic") as mock_yt_cls,
        ):
            client = YTMusicClient(auth_filepath="nonexistent.json")
            mock_yt_cls.assert_called_once_with()
            assert client.ytmusic is not None


class TestYTMusicHeadersParsingAndSetup:
    def test_curl_to_raw_headers_conversion(self) -> None:
        curl_cmd = (
            "curl 'https://music.youtube.com/' "
            "-H 'accept: */*' "
            "-b 'cookie1=val1; cookie2=val2' "
            "--header 'authorization: SAPISIDHASH 123'"
        )
        raw = YTMusicClient._curl_to_raw_headers(curl_cmd)
        assert "accept: */*" in raw
        assert "cookie: cookie1=val1; cookie2=val2" in raw
        assert "authorization: SAPISIDHASH 123" in raw

    def test_parse_raw_or_curl_headers(self) -> None:
        raw_text = "Host: music.youtube.com\nCookie: session=12345\n:method: GET"
        parsed = YTMusicClient.parse_raw_or_curl_headers(raw_text)
        assert parsed["host"] == "music.youtube.com"
        assert parsed["cookie"] == "session=12345"
        assert ":method" not in parsed

    def test_setup_headers_auth_success(self) -> None:
        raw_input = "cookie: session_token=abc123xyz\nuser-agent: Mozilla/5.0"
        with patch("ytmusicapi.auth.browser.setup_browser") as mock_setup_browser:
            YTMusicClient.setup_headers_auth(output_filepath="out.json", raw_input=raw_input)
            mock_setup_browser.assert_called_once_with(filepath="out.json", headers_raw=raw_input)

    def test_setup_headers_auth_missing_cookie_raises_error(self) -> None:
        raw_input = "user-agent: Mozilla/5.0\naccept: text/html"
        with pytest.raises(YTMusicAuthError, match="Missing 'cookie' header"):
            YTMusicClient.setup_headers_auth(output_filepath="out.json", raw_input=raw_input)


class TestYTMusicGetPlaylist:
    def test_get_playlist_success(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked

        mock_yt.get_playlist.return_value = {
            "title": "Workout Mix",
            "description": "High energy beats",
            "thumbnails": [{"url": "small.jpg"}, {"url": "large.jpg"}],
            "tracks": [
                {
                    "title": "Eye of the Tiger",
                    "artists": [{"name": "Survivor"}],
                    "album": {"name": "Rocky III"},
                    "duration_seconds": 245,
                    "videoId": "vid_survivor_1",
                },
                {
                    "title": "Stronger",
                    "artists": [{"name": "Kanye West"}],
                    "album": {"name": "Graduation"},
                    "duration_seconds": 312,
                    "videoId": "vid_kanye_2",
                },
            ],
        }

        playlist = client.get_playlist("PL_WORKOUT_123")

        assert playlist.id == "PL_WORKOUT_123"
        assert playlist.name == "Workout Mix"
        assert playlist.description == "High energy beats"
        assert playlist.cover_url == "large.jpg"
        assert len(playlist.tracks) == 2
        assert playlist.tracks[0].title == "Eye of the Tiger"
        assert playlist.tracks[0].duration_ms == 245000
        assert playlist.tracks[0].video_id == "vid_survivor_1"
        assert playlist.tracks[1].title == "Stronger"

    def test_get_playlist_error_raises_runtime_error(
        self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]
    ) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.get_playlist.side_effect = Exception("Playlist not accessible")

        with pytest.raises(PlaylistFetchError, match="Failed to fetch YTMusic playlist"):
            client.get_playlist("PL_INVALID")


class TestYTMusicGetLikedSongs:
    def test_get_liked_songs_success(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.get_liked_songs.return_value = {
            "title": "Música que te gusta",
            "description": "Your favorites",
            "thumbnails": [{"url": "http://img/lm.jpg"}],
            "tracks": [
                {
                    "title": "Favorite Song 1",
                    "artists": [{"name": "Artist A"}],
                    "album": {"name": "Album A"},
                    "duration_seconds": 210,
                    "videoId": "vid_fav_1",
                },
                {
                    "title": "Favorite Song 2",
                    "artists": [{"name": "Artist B"}],
                    "album": None,
                    "duration_seconds": 180,
                    "videoId": "vid_fav_2",
                },
            ],
        }

        liked = client.get_liked_songs()

        assert liked.id == "LM"
        assert liked.name == "Música que te gusta"
        assert liked.source == "YouTube Music"
        assert len(liked.tracks) == 2
        assert liked.tracks[0].title == "Favorite Song 1"
        assert liked.tracks[0].video_id == "vid_fav_1"
        assert liked.tracks[0].duration_ms == 210000

    def test_get_liked_songs_unauthenticated_raises_error(self) -> None:
        client = YTMusicClient.__new__(YTMusicClient)
        client.ytmusic = None
        with pytest.raises(YTMusicAuthError, match="YTMusic client is not initialized"):
            client.get_liked_songs()

    def test_get_liked_songs_api_failure_raises_error(
        self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]
    ) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.get_liked_songs.side_effect = Exception("Service unavailable")

        with pytest.raises(LikedSongsFetchError, match="Failed to fetch YouTube Music liked songs"):
            client.get_liked_songs()


class TestYTMusicGetExistingPlaylist:
    def test_get_existing_playlist_found(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked

        mock_yt.get_library_playlists.return_value = [
            {"title": "Favorites", "playlistId": "PL_FAV"},
            {"title": "Road Trip 2025", "playlistId": "PL_ROAD"},
        ]

        with patch.object(client, "get_playlist") as mock_get_pl:
            mock_get_pl.return_value = MagicMock(name="Loaded Playlist")
            result = client.get_existing_playlist("road trip 2025")

            assert result is not None
            mock_get_pl.assert_called_once_with("PL_ROAD")

    def test_get_existing_playlist_not_found(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.get_library_playlists.return_value = [{"title": "Jazz", "playlistId": "PL_JAZZ"}]

        assert client.get_existing_playlist("Rock") is None


class TestYTMusicSearchTrack:
    def test_search_track_isrc_strategy(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.search.return_value = [{"videoId": "isrc_vid_123"}]

        track = Track(title="Song", artists=["Artist"], album="Album", duration_ms=1000, isrc="US1234567890")
        vid = client.search_track(track)

        assert vid == "isrc_vid_123"
        mock_yt.search.assert_called_once_with(query="US1234567890", filter="songs")

    def test_search_track_artist_title_fallback(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.search.side_effect = [
            [],  # ISRC search returns empty list
            [{"videoId": "artist_title_vid_456"}],  # Artist+title search returns match
        ]

        track = Track(title="Song A", artists=["Artist B"], album="Album", duration_ms=1000, isrc="US999")
        vid = client.search_track(track)

        assert vid == "artist_title_vid_456"
        assert mock_yt.search.call_count == 2

    def test_search_track_title_fallback(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.search.side_effect = [
            [],  # Artist+title search empty
            [{"videoId": "title_vid_789"}],  # Title only search match
        ]

        track = Track(title="Unique Title", artists=[], album="Album", duration_ms=1000)
        vid = client.search_track(track)

        assert vid == "title_vid_789"
        assert mock_yt.search.call_count == 2

    def test_search_track_not_found(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.search.return_value = []

        track = Track(title="Nonexistent", artists=["Nobody"], album="Album", duration_ms=1000)
        assert client.search_track(track) is None


class TestYTMusicWriteOperations:
    def test_create_playlist(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.create_playlist.return_value = "PL_CREATED_123"

        playlist_id = client.create_playlist(title="New Playlist", description="Some desc")
        assert playlist_id == "PL_CREATED_123"
        mock_yt.create_playlist.assert_called_once_with(title="New Playlist", description="Some desc")

    def test_add_tracks_chunking(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        video_ids = [f"vid_{i}" for i in range(85)]

        client.add_tracks(playlist_id="PL_TARGET", track_ids=video_ids, chunk_size=50)

        assert mock_yt.add_playlist_items.call_count == 2
        mock_yt.add_playlist_items.assert_any_call(playlistId="PL_TARGET", videoIds=video_ids[:50])
        mock_yt.add_playlist_items.assert_any_call(playlistId="PL_TARGET", videoIds=video_ids[50:])

    def test_clear_playlist_with_items(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.get_playlist.return_value = {
            "tracks": [
                {"videoId": "v1", "setVideoId": "set1"},
                {"videoId": "v2", "setVideoId": "set2"},
            ]
        }

        client.clear_playlist("PL_CLEAR_ME")

        mock_yt.remove_playlist_items.assert_called_once_with(
            "PL_CLEAR_ME",
            [
                {"videoId": "v1", "setVideoId": "set1"},
                {"videoId": "v2", "setVideoId": "set2"},
            ],
        )

    def test_clear_playlist_empty(self, ytmusic_client_mocked: tuple[YTMusicClient, MagicMock]) -> None:
        client, mock_yt = ytmusic_client_mocked
        mock_yt.get_playlist.return_value = {"tracks": []}

        client.clear_playlist("PL_EMPTY")
        mock_yt.remove_playlist_items.assert_not_called()
