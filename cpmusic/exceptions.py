class CPMusicError(Exception):
    """Base exception for all cp-music errors."""

    pass


class SpotifyAuthError(CPMusicError):
    """Raised when Spotify authentication fails."""

    pass


class YouTubeMusicNetworkError(CPMusicError):
    """Raised when a network error occurs while communicating with YouTube Music."""

    pass


class RateLimitError(CPMusicError):
    """Raised when an API rate limit is hit."""

    pass


class NetworkError(CPMusicError):
    """Raised for generic network errors."""

    pass
