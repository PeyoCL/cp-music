"""
playlist_migrate.providers — Music streaming service clients conforming to MusicProvider.
"""

from __future__ import annotations

from playlist_migrate.providers.spotify import SpotifyClient
from playlist_migrate.providers.ytmusic import YTMusicClient

__all__ = ["SpotifyClient", "YTMusicClient"]
