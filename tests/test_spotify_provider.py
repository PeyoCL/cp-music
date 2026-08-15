"""
test_spotify_provider.py — Unit tests with mocks for SpotifyClient provider.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from playlist_migrate.exceptions import (
    LikedSongsFetchError,
    LikedSongsModifyError,
    PlaylistFetchError,
    SpotifyAuthError,
)
from playlist_migrate.models import Track
from playlist_migrate.providers.spotify import SpotifyClient


@pytest.fixture
def spotify_client_mocked() -> tuple[SpotifyClient, MagicMock]:
    """Creates a SpotifyClient instance with mocked spotipy.Spotify instance."""
    mock_sp = MagicMock()
    with (
        patch.dict("os.environ", {"SPOTIPY_CLIENT_ID": "mock_id", "SPOTIPY_CLIENT_SECRET": "mock_secret"}),
        patch("playlist_migrate.providers.spotify.SpotifyPKCE"),
        patch("playlist_migrate.providers.spotify.spotipy.Spotify", return_value=mock_sp),
    ):
        client = SpotifyClient(client_id="mock_id", client_secret="mock_secret")
        client.sp = mock_sp
        return client, mock_sp


class TestSpotifyAuth:
    def test_missing_credentials_raises_error(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(SpotifyAuthError, match="Missing Spotify credentials"),
        ):
            SpotifyClient(client_id=None, client_secret=None)

    def test_pkce_auth_success(self) -> None:
        with (
            patch.dict("os.environ", {"SPOTIPY_CLIENT_ID": "id", "SPOTIPY_CLIENT_SECRET": "secret"}),
            patch("playlist_migrate.providers.spotify.SpotifyPKCE") as mock_pkce,
            patch("playlist_migrate.providers.spotify.spotipy.Spotify") as mock_spotify_cls,
        ):
            client = SpotifyClient()
            mock_pkce.assert_called_once()
            mock_spotify_cls.assert_called_once()
            assert client.sp is not None

    def test_pkce_failure_falls_back_to_client_credentials(self) -> None:
        with (
            patch.dict("os.environ", {"SPOTIPY_CLIENT_ID": "id", "SPOTIPY_CLIENT_SECRET": "secret"}),
            patch("playlist_migrate.providers.spotify.SpotifyPKCE", side_effect=Exception("PKCE failed")),
            patch("playlist_migrate.providers.spotify.SpotifyClientCredentials") as mock_cc,
            patch("playlist_migrate.providers.spotify.spotipy.Spotify") as mock_spotify_cls,
        ):
            client = SpotifyClient()
            mock_cc.assert_called_once_with(client_id="id", client_secret="secret")
            mock_spotify_cls.assert_called_once()
            assert client.sp is not None


class TestSpotifyTrackParsing:
    def test_parse_valid_track(self) -> None:
        raw_track = {
            "name": "Bohemian Rhapsody",
            "type": "track",
            "id": "track_123",
            "artists": [{"name": "Queen"}, {"name": "Freddie"}],
            "album": {"name": "A Night at the Opera"},
            "duration_ms": 354000,
            "external_ids": {"isrc": "GBUM71029604"},
        }
        track = SpotifyClient._parse_track(raw_track)
        assert track is not None
        assert track.title == "Bohemian Rhapsody"
        assert track.artists == ["Queen", "Freddie"]
        assert track.album == "A Night at the Opera"
        assert track.duration_ms == 354000
        assert track.isrc == "GBUM71029604"
        assert track.spotify_id == "track_123"

    def test_parse_invalid_or_non_track_returns_none(self) -> None:
        assert SpotifyClient._parse_track({}) is None
        assert SpotifyClient._parse_track({"name": "Episode 1", "type": "episode"}) is None
        assert SpotifyClient._parse_track({"name": ""}) is None


class TestSpotifyGetPlaylist:
    def test_get_playlist_pagination(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked

        mock_sp.playlist.return_value = {
            "name": "Rock Classics",
            "description": "Best rock songs",
            "images": [{"url": "https://img.spotify.com/cover.jpg"}],
        }

        # Page 1 (2 items, total 3)
        page_1 = {
            "total": 3,
            "items": [
                {
                    "track": {
                        "name": "Song 1",
                        "type": "track",
                        "id": "s1",
                        "artists": [{"name": "Band A"}],
                        "album": {"name": "Album 1"},
                        "duration_ms": 200000,
                    }
                },
                {
                    "track": {
                        "name": "Song 2",
                        "type": "track",
                        "id": "s2",
                        "artists": [{"name": "Band B"}],
                        "album": {"name": "Album 2"},
                        "duration_ms": 210000,
                    }
                },
            ],
        }

        # Page 2 (1 item, total 3)
        page_2 = {
            "total": 3,
            "items": [
                {
                    "track": {
                        "name": "Song 3",
                        "type": "track",
                        "id": "s3",
                        "artists": [{"name": "Band C"}],
                        "album": {"name": "Album 3"},
                        "duration_ms": 220000,
                    }
                }
            ],
        }

        mock_sp.playlist_items.side_effect = [page_1, page_2]

        playlist = client.get_playlist("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")

        assert playlist.id == "37i9dQZF1DXcBWIGoYBM5M"
        assert playlist.name == "Rock Classics"
        assert playlist.description == "Best rock songs"
        assert playlist.cover_url == "https://img.spotify.com/cover.jpg"
        assert len(playlist.tracks) == 3
        assert playlist.tracks[0].title == "Song 1"
        assert playlist.tracks[2].title == "Song 3"

    def test_get_playlist_api_failure_raises_runtime_error(
        self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]
    ) -> None:
        client, mock_sp = spotify_client_mocked
        mock_sp.playlist.side_effect = Exception("Not found")

        with pytest.raises(PlaylistFetchError, match="Failed to fetch Spotify playlist"):
            client.get_playlist("invalid_id")


class TestSpotifyGetLikedSongs:
    def test_get_liked_songs_success(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked

        mock_sp.current_user_saved_tracks.side_effect = [
            {
                "total": 3,
                "items": [
                    {
                        "track": {
                            "name": "Favorite 1",
                            "artists": [{"name": "Artist 1"}],
                            "album": {"name": "Album 1"},
                            "duration_ms": 180000,
                            "external_ids": {"isrc": "US1111111111"},
                            "id": "track_fav_1",
                        }
                    },
                    {
                        "track": {
                            "name": "Favorite 2",
                            "artists": [{"name": "Artist 2"}],
                            "album": {"name": "Album 2"},
                            "duration_ms": 200000,
                            "external_ids": {},
                            "id": "track_fav_2",
                        }
                    },
                ],
            },
            {
                "total": 3,
                "items": [
                    {
                        "track": {
                            "name": "Favorite 3",
                            "artists": [{"name": "Artist 3"}],
                            "album": {"name": "Album 3"},
                            "duration_ms": 220000,
                            "external_ids": {"isrc": "US3333333333"},
                            "id": "track_fav_3",
                        }
                    }
                ],
            },
            {"total": 3, "items": []},
        ]

        liked = client.get_liked_songs()

        assert liked.id == "liked_songs"
        assert liked.name == "Tus Me Gusta"
        assert len(liked.tracks) == 3
        assert liked.tracks[0].title == "Favorite 1"
        assert liked.tracks[0].isrc == "US1111111111"
        assert liked.tracks[2].title == "Favorite 3"

    def test_get_liked_songs_unauthenticated_raises_error(self) -> None:
        client = SpotifyClient.__new__(SpotifyClient)
        client.sp = None
        with pytest.raises(SpotifyAuthError, match="Spotify client is not authenticated"):
            client.get_liked_songs()

    def test_get_liked_songs_api_failure_raises_error(
        self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]
    ) -> None:
        client, mock_sp = spotify_client_mocked
        mock_sp.current_user_saved_tracks.side_effect = Exception("API rate limit or connection error")

        with pytest.raises(LikedSongsFetchError, match="Failed to fetch Spotify liked songs"):
            client.get_liked_songs()


class TestSpotifyAddLikedSongs:
    def test_add_liked_songs_success_batched(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        track_ids = [f"spotify:track:id_{i}" for i in range(75)]

        client.add_liked_songs(track_ids, chunk_size=50)

        assert mock_sp.current_user_saved_tracks_add.call_count == 2
        mock_sp.current_user_saved_tracks_add.assert_any_call(tracks=[f"id_{i}" for i in range(50)])
        mock_sp.current_user_saved_tracks_add.assert_any_call(tracks=[f"id_{i}" for i in range(50, 75)])

    def test_add_liked_songs_unauthenticated_raises_error(self) -> None:
        client = SpotifyClient.__new__(SpotifyClient)
        client.sp = None
        with pytest.raises(SpotifyAuthError, match="Spotify client is not authenticated"):
            client.add_liked_songs(["id_1"])

    def test_add_liked_songs_api_failure_raises_error(
        self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]
    ) -> None:
        client, mock_sp = spotify_client_mocked
        mock_sp.current_user_saved_tracks_add.side_effect = Exception("API error")

        with pytest.raises(LikedSongsModifyError, match="Failed to save tracks to Spotify Liked Songs"):
            client.add_liked_songs(["id_1"])


class TestSpotifyGetExistingPlaylist:
    def test_get_existing_playlist_found(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked

        mock_sp.current_user_playlists.return_value = {
            "total": 2,
            "items": [
                {"name": "Chill Vibes", "id": "pl_1"},
                {"name": "Road Trip", "id": "pl_2"},
            ],
        }

        with patch.object(client, "get_playlist") as mock_get_pl:
            mock_get_pl.return_value = MagicMock(name="Loaded Playlist")
            result = client.get_existing_playlist("road trip")

            assert result is not None
            mock_get_pl.assert_called_once_with("pl_2")

    def test_get_existing_playlist_not_found(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        mock_sp.current_user_playlists.return_value = {"total": 1, "items": [{"name": "Jazz", "id": "pl_1"}]}

        assert client.get_existing_playlist("Classical") is None


class TestSpotifySearchTrack:
    def test_search_track_isrc_strategy(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        mock_sp.search.return_value = {
            "tracks": {
                "items": [{"uri": "spotify:track:matched_isrc", "name": "Song", "artists": [{"name": "Artist"}]}]
            }
        }

        track = Track(title="Song", artists=["Artist"], album="Album", duration_ms=1000, isrc="US1234567890")
        uri = client.search_track(track)

        assert uri == "spotify:track:matched_isrc"

    def test_search_track_artist_title_fallback(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        mock_sp.search.side_effect = [
            {"tracks": {"items": []}},  # ISRC fails
            {
                "tracks": {
                    "items": [
                        {
                            "uri": "spotify:track:matched_artist_title",
                            "name": "Song A",
                            "artists": [{"name": "Artist B"}],
                        }
                    ]
                }
            },
        ]

        track = Track(title="Song A", artists=["Artist B"], album="Album", duration_ms=1000, isrc="US999")
        uri = client.search_track(track)

        assert uri == "spotify:track:matched_artist_title"

    def test_search_track_not_found(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        mock_sp.search.return_value = {"tracks": {"items": []}}

        track = Track(title="Nonexistent", artists=["Ghost"], album="Void", duration_ms=1000)
        uri = client.search_track(track)

        assert uri is None


class TestSpotifyWriteOperations:
    def test_create_playlist(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        mock_sp.me.return_value = {"id": "user_456"}
        mock_sp.user_playlist_create.return_value = {"id": "new_pl_789"}

        playlist_id = client.create_playlist(title="My New List", description="Desc")
        assert playlist_id == "new_pl_789"
        mock_sp.user_playlist_create.assert_called_once_with(
            user="user_456", name="My New List", public=False, description="Desc"
        )

    def test_add_tracks_chunking(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        track_uris = [f"spotify:track:{i}" for i in range(150)]

        client.add_tracks(playlist_id="pl_123", track_ids=track_uris, chunk_size=100)

        assert mock_sp.playlist_add_items.call_count == 2
        mock_sp.playlist_add_items.assert_any_call(playlist_id="pl_123", items=track_uris[:100])
        mock_sp.playlist_add_items.assert_any_call(playlist_id="pl_123", items=track_uris[100:])

    def test_clear_playlist(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        client.clear_playlist("pl_123")
        mock_sp.playlist_replace_items.assert_called_once_with("pl_123", [])

    def test_replace_tracks(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        track_uris = [f"spotify:track:{i}" for i in range(120)]

        client.replace_tracks(playlist_id="pl_123", track_uris=track_uris)

        mock_sp.playlist_replace_items.assert_called_once_with("pl_123", track_uris[:100])
        mock_sp.playlist_add_items.assert_called_once_with(playlist_id="pl_123", items=track_uris[100:])

    def test_upload_cover_image(self, spotify_client_mocked: tuple[SpotifyClient, MagicMock]) -> None:
        client, mock_sp = spotify_client_mocked
        mock_response = MagicMock()
        mock_response.content = b"fake_image_bytes"

        with patch("playlist_migrate.providers.spotify.requests.get", return_value=mock_response) as mock_get:
            client.upload_cover_image("pl_123", "https://example.com/cover.jpg")

            mock_get.assert_called_once_with(
                "https://example.com/cover.jpg", headers={"User-Agent": "Mozilla/5.0"}, timeout=15
            )
            mock_sp.playlist_upload_cover_image.assert_called_once()
