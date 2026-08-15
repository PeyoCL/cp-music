# Adding a New Music Provider to cp-music

This project is designed to be easily extensible. If you want to add support for a new music streaming service (e.g., Apple Music, Tidal, Amazon Music), you only need to follow a few structural guidelines.

## 1. Implement the `MusicProvider` Protocol

To ensure seamless integration, any new client must conform to the `MusicProvider` structural type (Protocol) defined in `cpmusic/interfaces.py`. Because Python 3.12+ supports `typing.Protocol`, you don't even need to subclass it directly, you just need to implement its methods with the exact same signatures.

### Required Methods

Your client class (e.g., `AppleMusicClient`) must expose the following asynchronous or synchronous methods:

```python
from cpmusic.models import Playlist, Track
from typing import Optional

class AppleMusicClient:
    def get_playlist(self, identifier: str) -> Playlist:
        """Fetch a full playlist from your service including all tracks."""
        pass

    def get_existing_playlist(self, name: str) -> Optional[Playlist]:
        """Find a playlist by its exact name in the user's library."""
        pass

    def search_track(self, track: Track) -> Optional[str]:
        """Look up a track using the provided Track model. 
        You should return the native track ID string, or None if not found.
        Tip: Always prioritize searching by `track.isrc` if your API supports it!
        """
        pass

    def create_playlist(self, title: str, description: str = "") -> str:
        """Create a new playlist and return its native ID."""
        pass

    def add_tracks(self, playlist_id: str, track_ids: list[str], chunk_size: int = 50) -> None:
        """Add tracks to the playlist using chunks to respect API rate limits."""
        pass

    def clear_playlist(self, playlist_id: str) -> None:
        """Remove all items from an existing playlist for strict --sync operations."""
        pass
```

## 2. Using the Shared Models

Always use the standardized data classes defined in `cpmusic/models.py`:
- **`Track`**: Holds universal properties like `title`, `artists`, `album`, `isrc` and `duration_ms`. 
- **`Playlist`**: An agnostic container for tracks.

This ensures the `PlaylistMigrator` doesn't need to know where the data came from.

## 3. Integrating with `PlaylistMigrator`

Currently, `cpmusic/migrator.py` orchestrates the logic between source and destination providers. 
To wire up your new provider, simply instantiate it and pass it to the migrator or add a generic flow:

```python
# In cli.py or your entrypoint
apple_client = AppleMusicClient(...)
migrator = PlaylistMigrator(source_client=apple_client, target_client=spotify_client)
```

*(Note: If modifying the core migrator, ensure you adapt its internal method names to support a dynamic `source` and `target` provider pattern instead of hardcoding `spotify` and `ytmusic` variables).*

## 4. Error Handling & Rate Limiting

- Wrap all your external API calls with the `@with_retries` decorator located in `cpmusic.utils`.
- Raise `RateLimitError` or `NetworkError` from `cpmusic.exceptions` when appropriate so the migrator can back off and retry automatically.

## 5. Adding Tests

- Add a fixture for your new mocked client in `tests/conftest.py` (e.g., `mock_apple`).
- Ensure you verify both directions (e.g., `Apple Music → Spotify` and `Spotify → Apple Music`) in `tests/test_migrator.py`.
