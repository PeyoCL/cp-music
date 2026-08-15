"""
cpmusic.providers — Music streaming service clients conforming to MusicProvider.
"""

from __future__ import annotations

from cpmusic.providers.spotify import SpotifyClient
from cpmusic.providers.ytmusic import YTMusicClient

__all__ = ["SpotifyClient", "YTMusicClient"]
