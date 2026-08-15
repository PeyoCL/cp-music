"""
interfaces.py — Common interfaces for music service providers.

This module defines the structural types (Protocols) that any new music service
client must implement to be supported by the PlaylistMigrator.
"""

from typing import Protocol

from cpmusic.models import Playlist, Track


class MusicProvider(Protocol):
    """Protocol defining the required methods for any music service client.

    Any client class implementing these methods with matching signatures will
    automatically satisfy this interface without needing to explicitly inherit from it.
    """

    def get_playlist(self, identifier: str) -> Playlist:
        """Fetch a full playlist including all tracks.

        Args:
            identifier: The service-specific ID or URL for the playlist.

        Returns:
            A `Playlist` model populated with all tracks.
        """
        ...

    def get_existing_playlist(self, name: str) -> Playlist | None:
        """Find and return a user playlist with the given name, or None.

        Args:
            name: Playlist display name to search for.

        Returns:
            Fully populated `Playlist`, or None if not found.
        """
        ...

    def search_track(self, track: Track) -> str | None:
        """Search the service for a track and return its native ID (or URI).

        Args:
            track: The `Track` model to look up.

        Returns:
            The native service track ID string, or None if not found.
        """
        ...

    def create_playlist(self, title: str, description: str = "") -> str:
        """Create a new playlist for the authenticated user.

        Args:
            title: Playlist display name.
            description: Optional playlist description.

        Returns:
            The newly created playlist's native ID.
        """
        ...

    def add_tracks(self, playlist_id: str, track_ids: list[str], chunk_size: int) -> None:
        """Add a list of native track IDs to the specified playlist.

        Args:
            playlist_id: Target playlist ID.
            track_ids: List of native service track IDs/URIs to add.
            chunk_size: Safe batch size for the service API.
        """
        ...

    def clear_playlist(self, playlist_id: str) -> None:
        """Remove all tracks from the specified playlist.

        Args:
            playlist_id: Target playlist ID.
        """
        ...
