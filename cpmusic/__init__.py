"""
cp-music — Bidirectional playlist migration between Spotify and YouTube Music.

Supported directions:
  * Spotify  → YouTube Music  (migrate-to-ytmusic)
  * YouTube Music → Spotify   (migrate-to-spotify)

Both directions detect existing destination playlists and only add tracks
that are not already present, making every run fully idempotent.
"""

__version__ = "0.2.0"
