"""
exceptions.py — Domain-specific exceptions for playlist-migrate.

Defines a granular exception hierarchy for all error conditions across
the core migrator, CLI, and music service providers.
"""

from __future__ import annotations


class PlaylistMigrateError(Exception):
    """Base exception for all playlist-migrate domain errors."""

    pass


# Backward compatibility alias
CPMusicError = PlaylistMigrateError


class ProviderNotFoundError(PlaylistMigrateError):
    """Raised when a requested provider is not registered or supported."""

    pass


class AuthError(PlaylistMigrateError):
    """Base exception for authentication and credential failures."""

    pass


class SpotifyAuthError(AuthError):
    """Raised when Spotify authentication fails or credentials are missing."""

    pass


class YTMusicAuthError(AuthError):
    """Raised when YouTube Music authentication fails or headers/cookies are missing."""

    pass


class NetworkError(PlaylistMigrateError):
    """Raised when a network connectivity or HTTP communication failure occurs."""

    pass


class YouTubeMusicNetworkError(NetworkError):
    """Raised when a network error occurs while communicating with YouTube Music."""

    pass


class SpotifyNetworkError(NetworkError):
    """Raised when a network error occurs while communicating with Spotify."""

    pass


class RateLimitError(PlaylistMigrateError):
    """Raised when an API rate limit (HTTP 429) is hit on any music service."""

    pass


class PlaylistError(PlaylistMigrateError):
    """Base exception for playlist operations."""

    pass


class PlaylistNotFoundError(PlaylistError):
    """Raised when a requested playlist cannot be found on the service."""

    pass


class PlaylistFetchError(PlaylistError):
    """Raised when fetching playlist details or tracks fails."""

    pass


class PlaylistCreationError(PlaylistError):
    """Raised when creating a new playlist fails."""

    pass


class PlaylistModificationError(PlaylistError):
    """Raised when adding, clearing, or replacing tracks in a playlist fails."""

    pass


class CoverImageError(PlaylistMigrateError):
    """Raised when downloading or uploading a playlist cover image fails."""

    pass
