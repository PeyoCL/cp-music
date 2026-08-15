"""
matching.py — High-precision track matching and scoring for playlist-migrate.

Provides text normalization, noise reduction (remaster/live/feat suffixes),
and fuzzy candidate scoring to prevent false positive associations across platforms.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalize_text(s: str) -> str:
    """Normalize a string by lowercasing, removing diacritics/accents, and stripping punctuation.

    Args:
        s: Input text string.

    Returns:
        Cleaned, normalized string with collapsed whitespace.
    """
    if not s:
        return ""
    # Strip diacritics/accents (e.g., González -> Gonzalez, Capitán -> Capitan)
    n = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    n = n.lower()
    # Strip punctuation and special characters
    n = re.sub(r"[^\w\s]", " ", n)
    # Collapse multiple whitespace characters
    return re.sub(r"\s+", " ", n).strip()


def clean_track_title(title: str) -> str:
    """Remove remaster, live, anniversary, radio edit, edition, and feature suffixes from a track title.

    Args:
        title: Original track title (e.g. "Bohemian Rhapsody - Remastered 2011").

    Returns:
        Cleaned title suitable for cross-platform search (e.g. "Bohemian Rhapsody").
    """
    if not title:
        return ""

    pattern = (
        r"[\(\[\-–—]\s*("
        r"remaster(ed)?(\s*\d+)?|"
        r"\d{4}\s*remaster|"
        r"live(\s+at.*|\s+in.*)?|"
        r"radio\s+edit|"
        r"bonus\s+track|"
        r"deluxe(\s+edition)?|"
        r"special\s+edition|"
        r"anniversary(\s+edition)?|"
        r"version|"
        r"edit|"
        r"mono(\s+version)?|"
        r"stereo(\s+version)?|"
        r"official(\s+video|\s+audio|\s+music\s+video)?|"
        r"en\s+vivo|"
        r"en\s+directo|"
        r"(feat|ft)\.?\s+[^)\]]+"
        r")[\)\]]?"
    )
    cleaned = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else title.strip()


def text_similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings using normalized tokens and sequence matching.

    Returns:
        Float score between 0.0 (no match) and 1.0 (exact match).
    """
    na = normalize_text(a)
    nb = normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85 + 0.15 * (min(len(na), len(nb)) / max(len(na), len(nb)))

    ta = set(na.split())
    tb = set(nb.split())
    if ta and tb:
        overlap = len(ta & tb) / len(ta | tb)
        seq = SequenceMatcher(None, na, nb).ratio()
        return max(overlap, seq)

    return SequenceMatcher(None, na, nb).ratio()


def score_candidate(
    candidate_title: str,
    candidate_artists: list[str],
    target_title: str,
    target_artists: list[str],
    target_duration_ms: int = 0,
    candidate_duration_seconds: int = 0,
) -> float:
    """Score a candidate track result against target metadata.

    Evaluates title similarity, artist similarity, and duration closeness.
    Rejects results where title or artist similarity falls below minimum confidence.

    Args:
        candidate_title: Title of candidate result from music service.
        candidate_artists: List of artist names from candidate result.
        target_title: Original title of track being searched.
        target_artists: Original list of artists of track being searched.
        target_duration_ms: Duration in milliseconds of original track.
        candidate_duration_seconds: Duration in seconds of candidate track.

    Returns:
        Confidence score between 0.0 and 1.0. Returns 0.0 if confidence is insufficient.
    """
    clean_target = clean_track_title(target_title)
    clean_cand = clean_track_title(candidate_title)

    # Title similarity
    title_sim = max(
        text_similarity(target_title, candidate_title),
        text_similarity(clean_target, clean_cand),
        text_similarity(clean_target, candidate_title),
    )

    norm_cand_title = normalize_text(candidate_title)
    norm_target_title = normalize_text(clean_target)

    # In video results, title might be formatted as "Artist - Title"
    if norm_target_title and norm_target_title in norm_cand_title:
        title_sim = max(title_sim, 0.90)

    # Artist similarity
    artist_sim = 0.0
    if target_artists:
        for ta in target_artists:
            norm_ta = normalize_text(ta)
            for ca in candidate_artists:
                artist_sim = max(artist_sim, text_similarity(ta, ca))
            # Check if artist name appears inside candidate title string
            if norm_ta and norm_ta in norm_cand_title:
                artist_sim = max(artist_sim, 0.90)
    else:
        artist_sim = 0.5

    # Strict rejection thresholds:
    # If title does not match with at least 0.58 similarity, reject completely
    if title_sim < 0.58:
        return 0.0

    # If target artists exist and none match above 0.30, reject completely
    if target_artists and artist_sim < 0.30:
        return 0.0

    # Duration comparison (if available)
    dur_score = 1.0
    if target_duration_ms > 0 and candidate_duration_seconds > 0:
        target_sec = target_duration_ms / 1000.0
        delta = abs(target_sec - candidate_duration_seconds)
        if delta <= 15:
            dur_score = 1.0
        elif delta <= 40:
            dur_score = 0.9
        elif delta <= 90:
            dur_score = 0.7
        else:
            dur_score = 0.4

    # Weighted combined score
    total_score = (title_sim * 0.55) + (artist_sim * 0.35) + (dur_score * 0.10)
    return total_score
