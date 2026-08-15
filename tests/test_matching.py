"""
test_matching.py — Unit tests for the intelligent track matching and scoring module.
"""

from __future__ import annotations

import pytest

from playlist_migrate.matching import (
    clean_track_title,
    normalize_text,
    score_candidate,
    text_similarity,
)


class TestNormalizeText:
    def test_normalize_empty(self) -> None:
        assert normalize_text("") == ""

    def test_normalize_diacritics(self) -> None:
        assert normalize_text("Jorge González") == "jorge gonzalez"
        assert normalize_text("Capitán Memo") == "capitan memo"

    def test_normalize_punctuation_and_whitespace(self) -> None:
        assert normalize_text("Me Estai   Hueviando! (En Vivo)") == "me estai hueviando en vivo"
        assert normalize_text("Don't Stop Me Now...") == "don t stop me now"


class TestCleanTrackTitle:
    @pytest.mark.parametrize(
        ("raw_title", "expected_clean"),
        [
            ("Bohemian Rhapsody - Remastered 2011", "Bohemian Rhapsody"),
            ("Raining Blood (Live at Wembley)", "Raining Blood"),
            ("Il coro dei pompieri (2022 Remaster)", "Il coro dei pompieri"),
            ("Robots, Eres Formidable (En Vivo)", "Robots, Eres Formidable"),
            ("Song Title [Deluxe Edition]", "Song Title"),
            ("Track Name - Radio Edit", "Track Name"),
            ("Hit Song (feat. Other Artist)", "Hit Song"),
            ("Classic - 2011 Remaster", "Classic"),
            ("Simple Title", "Simple Title"),
        ],
    )
    def test_clean_track_title(self, raw_title: str, expected_clean: str) -> None:
        assert clean_track_title(raw_title) == expected_clean


class TestTextSimilarity:
    def test_exact_match(self) -> None:
        assert text_similarity("Bohemian Rhapsody", "Bohemian Rhapsody") == 1.0

    def test_accent_insensitive_match(self) -> None:
        assert text_similarity("Jorge González", "Jorge Gonzalez") == 1.0

    def test_substring_containment(self) -> None:
        score = text_similarity("Bohemian Rhapsody", "Bohemian Rhapsody (Live Aid)")
        assert score >= 0.85

    def test_completely_dissimilar(self) -> None:
        score = text_similarity("Bohemian Rhapsody", "Twinkle Twinkle Little Star")
        assert score < 0.20


class TestScoreCandidate:
    def test_exact_match_high_score(self) -> None:
        score = score_candidate(
            candidate_title="Raining Blood",
            candidate_artists=["Slayer"],
            target_title="Raining Blood",
            target_artists=["Slayer"],
            target_duration_ms=254000,
            candidate_duration_seconds=254,
        )
        assert score >= 0.95

    def test_remaster_suffix_match(self) -> None:
        score = score_candidate(
            candidate_title="Bohemian Rhapsody (Live Aid)",
            candidate_artists=["Queen"],
            target_title="Bohemian Rhapsody - Remastered 2011",
            target_artists=["Queen"],
            target_duration_ms=354000,
            candidate_duration_seconds=350,
        )
        assert score >= 0.85

    def test_rejects_different_song_by_same_artist(self) -> None:
        # Same artist, completely different title
        score = score_candidate(
            candidate_title="Necesito Poder Respirar",
            candidate_artists=["Jorge Gonzalez"],
            target_title="Pobrecito Mortal",
            target_artists=["Jorge González"],
            target_duration_ms=230000,
            candidate_duration_seconds=230,
        )
        assert score == 0.0

    def test_rejects_unrelated_isrc_false_positive(self) -> None:
        # Unrelated song returned by raw ISRC keyword search
        score = score_candidate(
            candidate_title="Twinkle Twinkle Little Star",
            candidate_artists=["Super Simple Songs"],
            target_title="Bohemian Rhapsody - Remastered 2011",
            target_artists=["Queen"],
            target_duration_ms=354000,
            candidate_duration_seconds=120,
        )
        assert score == 0.0

    def test_video_format_artist_in_title(self) -> None:
        score = score_candidate(
            candidate_title="Jorge Gonzalez - Pobrecito Mortal.",
            candidate_artists=[],
            target_title="Pobrecito Mortal",
            target_artists=["Jorge González"],
            target_duration_ms=230000,
            candidate_duration_seconds=232,
        )
        assert score >= 0.85
