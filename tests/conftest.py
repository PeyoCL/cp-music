from unittest.mock import MagicMock

import pytest

from playlist_migrate.providers import SpotifyClient, YTMusicClient


@pytest.fixture
def mock_sp() -> MagicMock:
    return MagicMock(spec=SpotifyClient)


@pytest.fixture
def mock_yt() -> MagicMock:
    return MagicMock(spec=YTMusicClient)
