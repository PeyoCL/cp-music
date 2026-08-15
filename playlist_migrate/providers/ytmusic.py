"""
ytmusic.py — YouTube Music client for playlist-migrate.

Wraps ytmusicapi to provide operations conforming to MusicProvider:

  * Authentication setup via browser-copied headers (setup_headers_auth).
  * Reading playlists from YouTube Music (get_playlist, get_existing_playlist).
  * Searching for tracks (search_track) using a 3-tier strategy.
  * Creating playlists (create_playlist).
  * Adding tracks to playlists (add_tracks).
  * Clearing playlists (clear_playlist).

Authentication:
    YouTube Music does not expose a public OAuth API for personal libraries.
    Instead, ytmusicapi authenticates using the request headers from a logged-in
    Chrome/Edge session exported as a cURL command.  Run:

        playlist-migrate setup-auth --from-file curl.txt

    once to generate ``headers_auth.json``, which is then reused for all
    subsequent operations.

Environment variables:
    YTMUSIC_AUTH_FILE   Path to the headers JSON file
                        (default: "headers_auth.json").
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from ytmusicapi import YTMusic

from playlist_migrate.exceptions import (
    LikedSongsFetchError,
    LikedSongsModifyError,
    PlaylistFetchError,
    PlaylistModificationError,
    YTMusicAuthError,
)
from playlist_migrate.models import Playlist, Track

logger = logging.getLogger(__name__)


class YTMusicClient:
    """Client for reading and writing YouTube Music playlists.

    Args:
        auth_filepath: Path to ``headers_auth.json``.  If omitted, the
                       ``YTMUSIC_AUTH_FILE`` env variable is used, falling
                       back to ``"headers_auth.json"`` in the current directory.
    """

    def __init__(self, auth_filepath: str | None = None) -> None:
        self.auth_filepath = auth_filepath or os.getenv("YTMUSIC_AUTH_FILE", "headers_auth.json")
        self.ytmusic: YTMusic | None = None
        self._initialize()

    # ------------------------------------------------------------------
    # Initialization & auth setup
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """Initialize YTMusic with browser headers or in read-only mode."""
        auth_path = Path(self.auth_filepath)
        if auth_path.exists():
            logger.info("Initializing YTMusic with auth file: %s", auth_path)
            self.ytmusic = YTMusic(str(auth_path))
        else:
            logger.warning(
                "Auth file '%s' not found. YTMusic initialized in read-only mode (write operations will fail).",
                self.auth_filepath,
            )
            self.ytmusic = YTMusic()

    @staticmethod
    def _curl_to_raw_headers(curl_text: str) -> str:
        """Convert a browser-copied cURL command into raw 'Key: Value' header lines.

        Handles both ``-H``/``--header`` arguments and ``-b``/``--cookie``
        arguments that Chrome sometimes separates.

        Args:
            curl_text: Full cURL command string pasted from Chrome DevTools.

        Returns:
            Newline-separated ``Key: Value`` header block.
        """
        lines: list[str] = []

        for match in re.finditer(r"(?:-H|--header)\s+[\"']([^\"']+)[\"']", curl_text):
            lines.append(match.group(1))

        for match in re.finditer(r"(?:-b|--cookie)\s+[\"']([^\"']+)[\"']", curl_text):
            lines.append(f"cookie: {match.group(1)}")

        return "\n".join(lines)

    @staticmethod
    def parse_raw_or_curl_headers(input_text: str) -> dict:
        """Parse raw header lines or a cURL command into a plain dict.

        Used mainly for validation/testing; actual auth setup delegates
        to ytmusicapi's ``setup_browser``.

        Args:
            input_text: Raw ``Key: Value`` headers or a cURL command string.

        Returns:
            Dict mapping lowercase header names to their values.
        """
        is_curl = re.search(r"(?:-H|--header)\s+[\"']", input_text)
        raw = YTMusicClient._curl_to_raw_headers(input_text) if is_curl else input_text

        headers: dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if ": " in line:
                key, _, val = line.partition(": ")
                headers[key.strip().lower()] = val.strip()
        return headers

    @staticmethod
    def setup_headers_auth(
        output_filepath: str = "headers_auth.json",
        raw_input: str | None = None,
    ) -> None:
        """Generate ``headers_auth.json`` from browser headers or a cURL snippet.

        Accepts raw ``Key: Value`` lines OR a full cURL command copied from
        Chrome/Edge DevTools.  Validates that a ``cookie`` header is present
        before delegating to ytmusicapi's ``setup_browser``.

        Args:
            output_filepath: Destination path for the JSON auth file.
            raw_input:       Header text to process.  If ``None``, the user
                             is prompted to paste headers interactively via
                             stdin (terminated with Ctrl+D).

        Raises:
            ValueError:     If no ``cookie`` header is found in the input.
            RuntimeError:   If ytmusicapi's ``setup_browser`` call fails.
        """
        import sys

        from ytmusicapi.auth.browser import setup_browser

        print("\n--- Setup YouTube Music Authentication ---")

        if not raw_input:
            print(
                "Pega tus cabeceras HTTP (formato 'Clave: Valor') o un comando "
                "cURL completo.\n"
                "👉 Cuando termines, presiona [ENTER] y luego [CTRL+D]:\n"
            )
            raw_input = sys.stdin.read()

        # Convert cURL → raw headers if necessary
        if re.search(r"(?:-H|--header)\s+[\"']", raw_input):
            print("🔄 Detectado formato cURL — convirtiendo a cabeceras raw...")
            raw_input = YTMusicClient._curl_to_raw_headers(raw_input)

        # Validate cookie presence
        headers_preview: dict[str, str] = {}
        for line in raw_input.splitlines():
            if ": " in line:
                k, _, v = line.partition(": ")
                headers_preview[k.strip().lower()] = v.strip()

        if "cookie" not in headers_preview:
            print(
                "\n❌ ERROR: No se encontró la cabecera 'cookie'.\n"
                "   ytmusicapi requiere las cookies de sesión de Google.\n\n"
                "💡 SOLUCIÓN:\n"
                "   1. En Chrome/Edge con music.youtube.com abierto, presiona "
                "Cmd+Option+I.\n"
                "   2. Pestaña Network → filtra por 'browse' → clic derecho → "
                "Copy → Copy as cURL (bash).\n"
                "   3. Guarda el texto copiado:\n"
                "      pbpaste > curl.txt\n"
                "   4. Ejecuta de nuevo:\n"
                "      playlist-migrate setup-auth --from-file curl.txt"
            )
            raise YTMusicAuthError("Missing 'cookie' header. Cannot authenticate with YouTube Music.")

        print(f"✅ Cookie encontrada. Generando '{output_filepath}' via ytmusicapi...")
        try:
            setup_browser(filepath=output_filepath, headers_raw=raw_input)
            print(f"✅ Autenticación guardada exitosamente en '{output_filepath}'.")
        except Exception as err:
            raise YTMusicAuthError(f"ytmusicapi setup_browser failed: {err}") from err

    # ------------------------------------------------------------------
    # Read operations (used when migrating Spotify → YTMusic)
    # ------------------------------------------------------------------

    def search_track(self, track: Track) -> str | None:
        """Search YouTube Music for a track and return its video ID.

        Uses a 3-tier matching strategy:
          1. ISRC code (highest confidence cross-platform match).
          2. "Artist - Title" query.
          3. Title-only fallback.

        Args:
            track: :class:`Track` to look up.

        Returns:
            YouTube Music video ID if found, otherwise ``None``.
        """
        if not self.ytmusic:
            return None

        def _first_video_id(results: list) -> str | None:
            if results:
                return results[0].get("videoId")
            return None

        # Strategy 1: ISRC
        if track.isrc:
            try:
                results = self.ytmusic.search(query=track.isrc, filter="songs")
                vid = _first_video_id(results)
                if vid:
                    logger.debug(
                        "Matched '%s' on YTMusic via ISRC (%s).",
                        track.title,
                        track.isrc,
                    )
                    return vid
            except Exception as err:
                logger.debug("YTMusic ISRC search failed for %s: %s", track.isrc, err)

        # Strategy 2: Artist + Title
        try:
            results = self.ytmusic.search(query=track.search_query, filter="songs")
            vid = _first_video_id(results)
            if vid:
                logger.debug("Matched '%s' on YTMusic via artist+title search.", track.title)
                return vid
        except Exception as err:
            logger.debug(
                "YTMusic artist+title search failed for '%s': %s",
                track.search_query,
                err,
            )

        # Strategy 3: Title fallback
        try:
            results = self.ytmusic.search(query=track.title, filter="songs")
            vid = _first_video_id(results)
            if vid:
                logger.debug("Matched '%s' on YTMusic via title fallback.", track.title)
                return vid
        except Exception as err:
            logger.debug("YTMusic title search failed for '%s': %s", track.title, err)

        logger.warning(
            "Could not find '%s' by %s on YouTube Music.",
            track.title,
            track.artist_name,
        )
        return None

    # ------------------------------------------------------------------
    # Read operations (used when migrating YTMusic → Spotify)
    # ------------------------------------------------------------------

    def get_playlist(self, playlist_id: str) -> Playlist:
        """Fetch a YouTube Music playlist with all its tracks.

        Handles pagination automatically for large playlists.

        Args:
            playlist_id: YouTube Music playlist ID (starts with ``PL``).

        Returns:
            :class:`Playlist` populated with all available tracks.

        Raises:
            RuntimeError: If the playlist cannot be fetched.
        """
        if not self.ytmusic:
            raise YTMusicAuthError("YTMusic client is not initialized. Run setup-auth first.")

        try:
            raw = self.ytmusic.get_playlist(playlistId=playlist_id, limit=None)
        except Exception as err:
            raise PlaylistFetchError(f"Failed to fetch YTMusic playlist '{playlist_id}': {err}") from err

        name = raw.get("title", "Migrated Playlist")
        description = raw.get("description", "") or "Migrated from YouTube Music"

        thumbnails = raw.get("thumbnails", [])
        cover_url = thumbnails[-1].get("url") if thumbnails else None

        tracks: list[Track] = []
        for item in raw.get("tracks", []):
            title = item.get("title")
            if not title:
                continue

            artists_raw = item.get("artists") or []
            artists = [a.get("name", "") for a in artists_raw if a.get("name")]

            album_info = item.get("album") or {}
            album = album_info.get("name", "Unknown Album")

            duration_seconds = item.get("duration_seconds") or 0
            video_id = item.get("videoId")

            tracks.append(
                Track(
                    title=title,
                    artists=artists,
                    album=album,
                    duration_ms=int(duration_seconds) * 1000,
                    video_id=video_id,
                )
            )

        logger.info("Loaded %d tracks from YTMusic playlist '%s'.", len(tracks), name)
        return Playlist(
            id=playlist_id,
            name=name,
            description=description,
            source="YouTube Music",
            tracks=tracks,
            cover_url=cover_url,
        )

    def get_liked_songs(self) -> Playlist:
        """Fetch the authenticated user's liked / favorite songs from YouTube Music.

        Uses the 'LM' (Liked Music) playlist in YouTube Music.

        Returns:
            :class:`Playlist` populated with all liked tracks.

        Raises:
            YTMusicAuthError: If client is not initialized.
            LikedSongsFetchError: If fetching fails.
        """
        if not self.ytmusic:
            raise YTMusicAuthError("YTMusic client is not initialized. Run setup-auth first.")

        try:
            raw = self.ytmusic.get_liked_songs(limit=None)
        except Exception as err:
            raise LikedSongsFetchError(f"Failed to fetch YouTube Music liked songs: {err}") from err

        name = raw.get("title", "Música que te gusta") or "Música que te gusta"
        description = raw.get("description", "") or "Liked Music from YouTube Music"
        thumbnails = raw.get("thumbnails", [])
        cover_url = thumbnails[-1].get("url") if thumbnails else None

        tracks: list[Track] = []
        for item in raw.get("tracks", []):
            title = item.get("title")
            if not title:
                continue

            artists = [a.get("name", "") for a in item.get("artists", []) if a.get("name")]
            album_info = item.get("album") or {}
            album = album_info.get("name", "Unknown Album") if isinstance(album_info, dict) else "Unknown Album"

            duration_seconds = item.get("duration_seconds") or 0
            video_id = item.get("videoId")

            tracks.append(
                Track(
                    title=title,
                    artists=artists or ["Unknown Artist"],
                    album=album,
                    duration_ms=int(duration_seconds) * 1000,
                    video_id=video_id,
                )
            )

        logger.info("Loaded %d liked songs from YouTube Music.", len(tracks))
        return Playlist(
            id="LM",
            name=name,
            description=description,
            source="YouTube Music",
            tracks=tracks,
            cover_url=cover_url,
        )

    def get_existing_playlist(self, name: str) -> Playlist | None:
        """Find a user-owned YouTube Music playlist by name.

        Iterates through the authenticated user's playlists and returns
        the first exact (case-insensitive) name match, fully populated.

        Args:
            name: Playlist display name to search for.

        Returns:
            Fully populated :class:`Playlist`, or ``None`` if not found.
        """
        if not self.ytmusic:
            return None

        try:
            playlists = self.ytmusic.get_library_playlists(limit=None)
        except Exception as err:
            logger.warning("Could not list YTMusic library playlists: %s", err)
            return None

        for pl in playlists:
            if (pl.get("title") or "").strip().lower() == name.strip().lower():
                playlist_id = pl.get("playlistId")
                if playlist_id:
                    logger.info(
                        "Found existing YTMusic playlist '%s' (ID: %s).",
                        name,
                        playlist_id,
                    )
                    return self.get_playlist(playlist_id)

        return None

    def get_playlist_video_ids(self, playlist_id: str) -> set[str]:
        """Return the set of video IDs already in a YTMusic playlist.

        Used to detect duplicates before adding new tracks.

        Args:
            playlist_id: YouTube Music playlist ID.

        Returns:
            Set of video ID strings (empty if the playlist cannot be read).
        """
        try:
            raw = self.ytmusic.get_playlist(playlistId=playlist_id, limit=None)
            return {item["videoId"] for item in raw.get("tracks", []) if item.get("videoId")}
        except Exception as err:
            logger.warning(
                "Could not read existing tracks for playlist %s: %s",
                playlist_id,
                err,
            )
            return set()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create_playlist(self, title: str, description: str = "") -> str:
        """Create a new YouTube Music playlist.

        Args:
            title:       Playlist display name.
            description: Optional description.

        Returns:
            New playlist ID string.

        Raises:
            RuntimeError: If the client is not authenticated or the API fails.
        """
        if not self.ytmusic:
            raise YTMusicAuthError("YTMusic client is not authenticated.")

        playlist_id = self.ytmusic.create_playlist(title=title, description=description)
        logger.info("Created YTMusic playlist '%s' (ID: %s).", title, playlist_id)
        return playlist_id

    def add_tracks(
        self,
        playlist_id: str,
        track_ids: list[str],
        chunk_size: int = 50,
    ) -> None:
        """Add video IDs to a YouTube Music playlist in safe-sized batches.

        Args:
            playlist_id: Target playlist ID.
            track_ids:   List of YouTube video IDs to add.
            chunk_size:  Batch size (ytmusicapi recommends ≤ 50 per call).

        Raises:
            YTMusicAuthError: If client is not authenticated.
            PlaylistModificationError: If a batch fails to be added.
        """
        if not self.ytmusic:
            raise YTMusicAuthError("YTMusic client is not authenticated.")

        for i in range(0, len(track_ids), chunk_size):
            chunk = track_ids[i : i + chunk_size]
            try:
                self.ytmusic.add_playlist_items(playlistId=playlist_id, videoIds=chunk)
                logger.info(
                    "Added batch of %d tracks to YTMusic playlist %s.",
                    len(chunk),
                    playlist_id,
                )
            except Exception as err:
                raise PlaylistModificationError(
                    f"Failed to add track batch to YTMusic playlist {playlist_id}: {err}"
                ) from err

    def clear_playlist(self, playlist_id: str) -> None:
        """Remove all tracks from a YouTube Music playlist.

        Args:
            playlist_id: Target playlist ID.

        Raises:
            YTMusicAuthError: If client is not authenticated.
            PlaylistModificationError: If clearing fails.
        """
        if not self.ytmusic:
            raise YTMusicAuthError("YTMusic client is not authenticated.")

        try:
            raw = self.ytmusic.get_playlist(playlistId=playlist_id, limit=None)
            tracks_to_remove = []
            for item in raw.get("tracks", []):
                if item.get("videoId") and item.get("setVideoId"):
                    tracks_to_remove.append({"videoId": item["videoId"], "setVideoId": item["setVideoId"]})

            # ytmusicapi allows removing all items by passing the list of dicts
            if tracks_to_remove:
                self.ytmusic.remove_playlist_items(playlist_id, tracks_to_remove)
                logger.info("Cleared %d tracks from YTMusic playlist %s.", len(tracks_to_remove), playlist_id)
            else:
                logger.info("YTMusic playlist %s is already empty.", playlist_id)
        except Exception as err:
            raise PlaylistModificationError(f"Failed to clear YTMusic playlist {playlist_id}: {err}") from err

    def add_liked_songs(self, track_ids: list[str]) -> None:
        """Add / rate songs as 'LIKE' (thumbs up) in the authenticated user's YouTube Music library.

        These tracks will directly appear in the system 'LM' (Música que te gusta) playlist.

        Args:
            track_ids: List of YouTube video IDs to rate as LIKE.

        Raises:
            YTMusicAuthError: If client is not authenticated.
            LikedSongsModifyError: If rating any track fails.
        """
        if not self.ytmusic:
            raise YTMusicAuthError("YTMusic client is not authenticated.")

        for video_id in track_ids:
            if not video_id:
                continue
            try:
                self.ytmusic.rate_song(videoId=video_id, rating="LIKE")
                logger.info("Rated video %s as LIKE in YouTube Music.", video_id)
            except Exception as err:
                raise LikedSongsModifyError(f"Failed to rate video {video_id} as LIKE: {err}") from err
