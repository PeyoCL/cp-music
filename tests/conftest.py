from unittest.mock import MagicMock

import pytest

from cpmusic.spotify_client import SpotifyClient
from cpmusic.ytmusic_client import YTMusicClient


@pytest.fixture
def mock_sp() -> MagicMock:
    return MagicMock(spec=SpotifyClient)


@pytest.fixture
def mock_yt() -> MagicMock:
    return MagicMock(spec=YTMusicClient)
