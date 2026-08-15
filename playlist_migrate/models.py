"""
models.py — Shared domain models for playlist-migrate.

Defines the core data structures (Track, Playlist, MigrationResult) used
by both the Spotify and YouTube Music clients, and by the migrator.

All dataclasses are kept intentionally thin: they carry data only, with a
handful of convenience properties that avoid duplicating logic at call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Track:
    """Represents a single audio track with its essential metadata.

    Attributes:
        title:       Song title as it appears on the source platform.
        artists:     Ordered list of artist names (primary artist first).
        album:       Album name, or "Unknown Album" when unavailable.
        duration_ms: Track duration in milliseconds (0 when unavailable).
        isrc:        International Standard Recording Code, used for
                     high-confidence cross-platform matching (optional).
        video_id:    YouTube / YouTube Music video ID (optional).
                     Populated when the track originates from YTMusic.
        spotify_id:  Spotify track URI / ID (optional).
                     Populated when the track originates from Spotify.
    """

    title: str
    artists: list[str]
    album: str
    duration_ms: int
    isrc: str | None = None
    video_id: str | None = None  # YouTube Music native ID
    spotify_id: str | None = None  # Spotify track ID

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def artist_name(self) -> str:
        """Comma-separated string of all contributing artist names."""
        return ", ".join(self.artists)

    @property
    def search_query(self) -> str:
        """Primary artist + title, suitable as a music search query."""
        if self.artists:
            return f"{self.artists[0]} - {self.title}"
        return self.title

    @property
    def display_name(self) -> str:
        """Human-readable label shown in CLI output."""
        return f"{self.artist_name} — {self.title}"


# ---------------------------------------------------------------------------
# Generic Playlist
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Playlist:
    """Platform-agnostic container for a playlist and its tracks.

    Attributes:
        id:          Native playlist identifier on the source platform.
        name:        Playlist display name.
        description: Optional editorial description.
        tracks:      Ordered list of :class:`Track` objects.
        source:      Human-readable platform label (e.g. "Spotify",
                     "YouTube Music").
    """

    id: str
    name: str
    description: str
    source: str
    tracks: list[Track] = field(default_factory=list)
    cover_url: str | None = None


# ---------------------------------------------------------------------------
# Legacy alias kept for backward compatibility
# ---------------------------------------------------------------------------

#: Alias preserved so existing code that imports ``SpotifyPlaylist`` still works.
SpotifyPlaylist = Playlist


# ---------------------------------------------------------------------------
# MigrationResult
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MigrationResult:
    """Encapsulates the outcome and statistics of a playlist migration.

    Attributes:
        playlist_name:    Name used for the destination playlist.
        target_playlist_id: Native ID of the newly created (or updated)
                          destination playlist.
        direction:        String describing which way the migration ran (e.g., "Spotify → YouTube Music").
        total_tracks:     Total number of tracks in the source playlist.
        migrated_count:   Number of tracks successfully added.
        skipped_count:    Tracks already present in an existing playlist
                          (skipped to avoid duplicates).
        failed_tracks:    Tracks that could not be matched on the target
                          platform.
    """

    playlist_name: str
    target_playlist_id: str
    direction: str
    total_tracks: int
    migrated_count: int
    skipped_count: int = 0
    failed_tracks: list[Track] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def success_rate(self) -> float:
        """Percentage of source tracks successfully matched & added.

        Skipped tracks (already present) count as successful.
        """
        if self.total_tracks == 0:
            return 0.0
        effective = self.migrated_count + self.skipped_count
        return (effective / self.total_tracks) * 100
