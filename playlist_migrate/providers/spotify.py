"""
spotify.py — Spotify API client for playlist-migrate.

Handles authentication (OAuth2 PKCE for private playlists, Client Credentials
fallback for public-only access) and provides operations to conform to MusicProvider:

  * get_playlist()          — Fetch a Spotify playlist with all tracks.
  * search_track()          — Search Spotify for a track by title/artist/ISRC.
  * create_playlist()       — Create a new Spotify playlist.
  * add_tracks()            — Add tracks to a Spotify playlist.
  * clear_playlist()        — Remove all tracks from a Spotify playlist.
  * get_existing_playlist() — Find a playlist by name in the user's library.
  * upload_cover_image()    — Upload a custom cover image to a playlist.

Environment variables (loaded from .env):
  SPOTIPY_CLIENT_ID       Spotify app client ID (required)
  SPOTIPY_CLIENT_SECRET   Spotify app client secret (required)
  SPOTIPY_REDIRECT_URI    OAuth redirect URI (default: http://127.0.0.1:8888/callback)
"""

from __future__ import annotations

import base64
import logging
import os
import re

import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyPKCE

from playlist_migrate.exceptions import (
    LikedSongsFetchError,
    LikedSongsModifyError,
    PlaylistCreationError,
    PlaylistFetchError,
    PlaylistModificationError,
    SpotifyAuthError,
)
from playlist_migrate.models import Playlist, Track

logger = logging.getLogger(__name__)


class SpotifyClient:
    """Client for reading playlists from Spotify and creating new ones.

    Authenticates via PKCE (supports private playlists) with automatic
    fallback to Client Credentials (public playlists only).

    Args:
        client_id:     Spotify app client ID. Defaults to env var
                       ``SPOTIPY_CLIENT_ID``.
        client_secret: Spotify app client secret. Defaults to env var
                       ``SPOTIPY_CLIENT_SECRET``.
    """

    # Scopes required for reading and writing user playlists & library
    _PKCE_SCOPES = (
        "playlist-read-private "
        "playlist-read-collaborative "
        "playlist-modify-public "
        "playlist-modify-private "
        "ugc-image-upload "
        "user-library-read "
        "user-library-modify"
    )

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.client_id = client_id or os.getenv("SPOTIPY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SPOTIPY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

        self.sp: spotipy.Spotify | None = None
        self._authenticate()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self) -> None:
        """Authenticate with Spotify using PKCE (preferred) or Client Credentials.

        PKCE opens the browser and starts a local server on 127.0.0.1 to
        capture the OAuth callback automatically — no copy-pasting of URLs.
        Falls back to Client Credentials (public playlists only) on failure.
        """
        if not (self.client_id and self.client_secret):
            raise SpotifyAuthError(
                "Missing Spotify credentials. Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in your .env file."
            )

        try:
            auth_manager = SpotifyPKCE(
                client_id=self.client_id,
                redirect_uri=self.redirect_uri,
                scope=self._PKCE_SCOPES,
                open_browser=True,
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            logger.info("Authenticated with Spotify via PKCE (private playlists supported).")
        except Exception as err:
            logger.warning(
                "PKCE auth failed (%s). Falling back to Client Credentials "
                "(public playlists only — write operations will not work).",
                err,
            )
            self.sp = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                )
            )
            logger.info("Authenticated with Spotify via Client Credentials (public only).")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def extract_playlist_id(url_or_id: str) -> str:
        """Return the bare playlist ID from a Spotify URL or raw ID string.

        Handles URLs such as:
          https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc
        """
        match = re.search(r"playlist[/:]([a-zA-Z0-9]+)", url_or_id)
        if match:
            return match.group(1)
        return url_or_id

    @staticmethod
    def _parse_track(track_info: dict) -> Track | None:
        """Convert a raw Spotify track dict into a :class:`Track`.

        Returns ``None`` for local files, episodes, or items with no title.
        """
        if not track_info or not track_info.get("name"):
            return None

        # Skip non-track types (podcasts, local files)
        if track_info.get("type") not in ("track", None):
            return None

        artists = [a["name"] for a in track_info.get("artists", []) if "name" in a]
        return Track(
            title=track_info["name"],
            artists=artists,
            album=track_info.get("album", {}).get("name", "Unknown Album"),
            duration_ms=track_info.get("duration_ms", 0),
            isrc=track_info.get("external_ids", {}).get("isrc"),
            spotify_id=track_info.get("id"),
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_playlist(self, url_or_id: str) -> Playlist:
        """Fetch a full Spotify playlist including all tracks (handles pagination).

        Args:
            url_or_id: Spotify playlist URL or bare playlist ID.

        Returns:
            :class:`Playlist` populated with all available tracks.

        Raises:
            RuntimeError: If the playlist cannot be fetched from the API.
        """
        playlist_id = self.extract_playlist_id(url_or_id)

        try:
            raw = self.sp.playlist(playlist_id, additional_types=("track",))
        except Exception as err:
            raise PlaylistFetchError(f"Failed to fetch Spotify playlist '{playlist_id}': {err}") from err

        name = raw.get("name", "Migrated Playlist")
        description = raw.get("description", "") or "Migrated from Spotify"
        images = raw.get("images", [])
        cover_url = images[0].get("url") if images else None

        tracks: list[Track] = []
        offset, limit = 0, 100

        while True:
            try:
                page = self.sp.playlist_items(
                    playlist_id,
                    limit=limit,
                    offset=offset,
                    additional_types=("track",),
                )
            except Exception as err:
                logger.error("Failed to fetch tracks at offset %d: %s", offset, err)
                break

            items = page.get("items", [])
            if not items:
                break

            for item in items:
                # Spotify API may wrap the track under 'track' or 'item'
                raw_track = item.get("track") or item.get("item")
                parsed = self._parse_track(raw_track)
                if parsed:
                    tracks.append(parsed)

            offset += len(items)
            if offset >= (page.get("total") or 0):
                break

        logger.info("Loaded %d tracks from Spotify playlist '%s'.", len(tracks), name)
        return Playlist(
            id=playlist_id,
            name=name,
            description=description,
            source="Spotify",
            tracks=tracks,
            cover_url=cover_url,
        )

    def get_liked_songs(self) -> Playlist:
        """Fetch the authenticated user's liked / saved tracks from Spotify.

        Requires PKCE authentication with the ``user-library-read`` scope.

        Returns:
            :class:`Playlist` populated with all user liked tracks.

        Raises:
            SpotifyAuthError: If client is not authenticated with Spotify.
            LikedSongsFetchError: If the API call fails.
        """
        if not self.sp:
            raise SpotifyAuthError("Spotify client is not authenticated.")

        tracks: list[Track] = []
        offset, limit = 0, 50

        while True:
            try:
                page = self.sp.current_user_saved_tracks(limit=limit, offset=offset)
            except Exception as err:
                raise LikedSongsFetchError(f"Failed to fetch Spotify liked songs at offset {offset}: {err}") from err

            items = page.get("items", [])
            if not items:
                break

            for item in items:
                raw_track = item.get("track") or item.get("item")
                parsed = self._parse_track(raw_track)
                if parsed:
                    tracks.append(parsed)

            offset += len(items)
            if offset >= (page.get("total") or 0):
                break

        logger.info("Loaded %d liked songs from Spotify.", len(tracks))
        return Playlist(
            id="liked_songs",
            name="Tus Me Gusta",
            description="Liked Songs from Spotify",
            source="Spotify",
            tracks=tracks,
            cover_url=None,
        )

    def get_existing_playlist(self, name: str) -> Playlist | None:
        """Find and return a user playlist with the given name, or None.

        Only inspects the authenticated user's own playlists (up to 500).
        The first match (exact, case-insensitive) is returned.

        Args:
            name: Playlist display name to search for.

        Returns:
            Fully populated :class:`Playlist`, or ``None`` if not found.
        """
        if not self.sp:
            return None

        offset, limit = 0, 50
        while True:
            try:
                page = self.sp.current_user_playlists(limit=limit, offset=offset)
            except Exception as err:
                logger.warning("Could not list Spotify playlists: %s", err)
                break

            items = page.get("items", [])
            if not items:
                break

            for item in items:
                if (item.get("name") or "").strip().lower() == name.strip().lower():
                    logger.info(
                        "Found existing Spotify playlist '%s' (ID: %s).",
                        name,
                        item["id"],
                    )
                    # Return fully loaded playlist
                    return self.get_playlist(item["id"])

            offset += len(items)
            if offset >= (page.get("total") or 0):
                break

        return None

    # ------------------------------------------------------------------
    # Search (used when migrating YTMusic → Spotify)
    # ------------------------------------------------------------------

    def search_track(self, track: Track) -> str | None:
        """Search Spotify for a track and return its URI, or None.

        Uses a multi-tiered strategy:
          1. Search by ISRC (highest confidence, if available).
          2. Search by "Artist - Title" query.
          3. Search by Title only (broadest fallback).

        Args:
            track: :class:`Track` to search for.

        Returns:
            Spotify track URI (``spotify:track:<id>``) if found, else None.
        """
        if not self.sp:
            return None

        def _first_uri(results: dict) -> str | None:
            """Extract the first track URI from a Spotify search response."""
            items = results.get("tracks", {}).get("items", [])
            if items:
                return items[0].get("uri")
            return None

        # Strategy 1: ISRC lookup (most accurate cross-platform identifier)
        if track.isrc:
            try:
                results = self.sp.search(q=f"isrc:{track.isrc}", type="track", limit=1)
                uri = _first_uri(results)
                if uri:
                    logger.debug(
                        "Matched '%s' on Spotify via ISRC (%s).",
                        track.title,
                        track.isrc,
                    )
                    return uri
            except Exception as err:
                logger.debug("Spotify ISRC search failed for %s: %s", track.isrc, err)

        # Strategy 2: Artist + Title
        try:
            results = self.sp.search(
                q=f"artist:{track.artists[0] if track.artists else ''} track:{track.title}",
                type="track",
                limit=1,
            )
            uri = _first_uri(results)
            if uri:
                logger.debug("Matched '%s' on Spotify via artist+title search.", track.title)
                return uri
        except Exception as err:
            logger.debug("Spotify artist+title search failed for '%s': %s", track.title, err)

        # Strategy 3: Title fallback
        try:
            results = self.sp.search(q=track.title, type="track", limit=1)
            uri = _first_uri(results)
            if uri:
                logger.debug("Matched '%s' on Spotify via title fallback.", track.title)
                return uri
        except Exception as err:
            logger.debug("Spotify title search failed for '%s': %s", track.title, err)

        logger.warning(
            "Could not find '%s' by %s on Spotify.",
            track.title,
            track.artist_name,
        )
        return None

    # ------------------------------------------------------------------
    # Write operations (used when migrating YTMusic → Spotify)
    # ------------------------------------------------------------------

    def create_playlist(self, title: str, description: str = "") -> str:
        """Create a new Spotify playlist for the authenticated user.

        Args:
            title:       Playlist display name.
            description: Optional playlist description.

        Returns:
            Spotify playlist ID of the newly created playlist.

        Raises:
            RuntimeError: If the API call fails.
        """
        if not self.sp:
            raise SpotifyAuthError("Spotify client is not authenticated.")

        try:
            user_id = self.sp.me()["id"]
            result = self.sp.user_playlist_create(
                user=user_id,
                name=title,
                public=False,
                description=description,
            )
            playlist_id: str = result["id"]
            logger.info("Created Spotify playlist '%s' (ID: %s).", title, playlist_id)
            return playlist_id
        except Exception as err:
            raise PlaylistCreationError(f"Failed to create Spotify playlist '{title}': {err}") from err

    def add_tracks(
        self,
        playlist_id: str,
        track_ids: list[str],
        chunk_size: int = 100,
    ) -> None:
        """Add track URIs to a Spotify playlist in safe-sized batches.

        Spotify's API limit is 100 tracks per request.

        Args:
            playlist_id: Target Spotify playlist ID.
            track_ids:   List of ``spotify:track:<id>`` URIs to add.
            chunk_size:  Batch size (max 100 per Spotify API limit).

        Raises:
            SpotifyAuthError: If client is not authenticated.
            PlaylistModificationError: If any batch fails to be added.
        """
        if not self.sp:
            raise SpotifyAuthError("Spotify client is not authenticated.")

        for i in range(0, len(track_ids), chunk_size):
            chunk = track_ids[i : i + chunk_size]
            try:
                self.sp.playlist_add_items(playlist_id=playlist_id, items=chunk)
                logger.info(
                    "Added batch of %d tracks to Spotify playlist %s.",
                    len(chunk),
                    playlist_id,
                )
            except Exception as err:
                raise PlaylistModificationError(
                    f"Failed to add track batch to Spotify playlist {playlist_id}: {err}"
                ) from err

    def clear_playlist(self, playlist_id: str) -> None:
        """Remove all tracks from a Spotify playlist by replacing it with an empty list.

        Args:
            playlist_id: Target Spotify playlist ID.

        Raises:
            SpotifyAuthError: If client is not authenticated.
            PlaylistModificationError: If clearing fails.
        """
        if not self.sp:
            raise SpotifyAuthError("Spotify client is not authenticated.")

        try:
            self.sp.playlist_replace_items(playlist_id, [])
            logger.info("Cleared Spotify playlist %s.", playlist_id)
        except Exception as err:
            raise PlaylistModificationError(f"Failed to clear Spotify playlist {playlist_id}: {err}") from err

    def replace_tracks(self, playlist_id: str, track_uris: list[str]) -> None:
        """Replace all tracks in a Spotify playlist with the given URIs.

        Spotify allows replacing up to 100 items at once. For larger lists,
        the first 100 are replaced, and the remainder are added in batches.

        Args:
            playlist_id: Target Spotify playlist ID.
            track_uris:  List of ``spotify:track:<id>`` URIs to set.

        Raises:
            SpotifyAuthError: If client is not authenticated.
            PlaylistModificationError: If replacement fails.
        """
        if not self.sp:
            raise SpotifyAuthError("Spotify client is not authenticated.")

        if not track_uris:
            # If empty, just replace with an empty list
            self.clear_playlist(playlist_id)
            return

        # Replace first 100
        first_batch = track_uris[:100]
        try:
            self.sp.playlist_replace_items(playlist_id, first_batch)
            logger.info(
                "Replaced items in Spotify playlist %s with first batch of %d tracks.", playlist_id, len(first_batch)
            )
        except Exception as err:
            raise PlaylistModificationError(
                f"Failed to replace tracks in Spotify playlist {playlist_id}: {err}"
            ) from err

        # Add the rest in batches
        if len(track_uris) > 100:
            self.add_tracks(playlist_id, track_uris[100:])

    def upload_cover_image(self, playlist_id: str, image_url: str) -> None:
        """Download an image from a URL and upload it as the Spotify playlist cover.

        Args:
            playlist_id: Target Spotify playlist ID.
            image_url: URL of the source image.

        Raises:
            SpotifyAuthError: If client is not authenticated.
        """
        if not self.sp:
            raise SpotifyAuthError("Spotify client is not authenticated.")

        try:
            response = requests.get(image_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            response.raise_for_status()
            b64_image = base64.b64encode(response.content).decode("utf-8")
            self.sp.playlist_upload_cover_image(playlist_id, b64_image)
            logger.info("Successfully updated cover image for Spotify playlist %s", playlist_id)
        except Exception as err:
            logger.warning("Failed to upload cover image to Spotify: %s", err)

    def add_liked_songs(self, track_ids: list[str], chunk_size: int = 50) -> None:
        """Save / like tracks in the authenticated user's Spotify library (/collection/tracks).

        Spotify API limit is 50 tracks per batch.

        Args:
            track_ids:  List of Spotify track URIs or IDs to save.
            chunk_size: Batch size (max 50).

        Raises:
            SpotifyAuthError: If client is not authenticated.
            LikedSongsModifyError: If saving tracks fails.
        """
        if not self.sp:
            raise SpotifyAuthError("Spotify client is not authenticated.")

        clean_ids = [tid.removeprefix("spotify:track:") for tid in track_ids if tid]
        for i in range(0, len(clean_ids), chunk_size):
            chunk = clean_ids[i : i + chunk_size]
            try:
                self.sp.current_user_saved_tracks_add(tracks=chunk)
                logger.info("Saved batch of %d tracks to Spotify Liked Songs library.", len(chunk))
            except Exception as err:
                raise LikedSongsModifyError(f"Failed to save tracks to Spotify Liked Songs: {err}") from err
