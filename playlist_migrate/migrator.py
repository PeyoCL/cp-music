"""
migrator.py — Core orchestration for playlist-migrate bidirectional playlist migration.

This module provides :class:`PlaylistMigrator`, which coordinates the full
migration pipeline generically across any MusicProvider.
"""

from __future__ import annotations

import asyncio
import logging

from playlist_migrate.exceptions import ProviderNotFoundError
from playlist_migrate.interfaces import MusicProvider
from playlist_migrate.models import (
    MigrationResult,
    Playlist,
    Track,
)
from playlist_migrate.utils import with_retries

logger = logging.getLogger(__name__)


class PlaylistMigrator:
    """Orchestrates playlist migration generically between any two providers.

    Args:
        providers: Dictionary mapping provider ID (e.g. 'spotify') to a MusicProvider instance.
    """

    def __init__(
        self,
        providers: dict[str, MusicProvider],
    ) -> None:
        self.providers = providers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def migrate(
        self,
        source_id: str,
        target_id: str,
        playlist_identifier: str,
        target_name: str | None = None,
        sync: bool = False,
    ) -> MigrationResult:
        """Migrate a playlist from a source provider to a target provider.

        Args:
            source_id: Provider ID of the source platform (e.g. 'spotify').
            target_id: Provider ID of the target platform (e.g. 'ytmusic').
            playlist_identifier: Native playlist ID on the source platform.
            target_name: Override the destination playlist name.
            sync: If True, replace the target playlist contents to match exactly.
                  Otherwise, just add missing tracks (idempotent).
        """
        logger.info("Starting %s → %s migration: %s", source_id, target_id, playlist_identifier)

        source_provider = self.providers.get(source_id)
        target_provider = self.providers.get(target_id)

        if not source_provider:
            raise ProviderNotFoundError(f"Source provider '{source_id}' not found.")
        if not target_provider:
            raise ProviderNotFoundError(f"Target provider '{target_id}' not found.")

        source: Playlist = source_provider.get_playlist(playlist_identifier)
        dest_name = target_name or source.name

        direction_label = f"{source_id.title()} → {target_id.title()}"

        if not source.tracks:
            logger.warning("%s playlist '%s' is empty. Aborting.", source_id.title(), source.name)
            return self._empty_result(dest_name, direction_label)

        print(f"\n🎵 Searching {target_id.title()} for {len(source.tracks)} tracks...")
        track_ids, failed = await self._search_tracks(target_provider, tracks=source.tracks)

        dest_playlist_id, existing_pl = self._resolve_playlist(target_provider, dest_name, source, target_id)

        if sync:
            print("\n🔄 Sync mode: Replacing target playlist contents to match exactly...")
            valid_ids = [tid for tid in track_ids if tid]
            target_provider.clear_playlist(dest_playlist_id)
            if valid_ids:
                target_provider.add_tracks(playlist_id=dest_playlist_id, track_ids=valid_ids)
            skipped_count = 0
            migrated_count = len(valid_ids)
        else:
            existing_ids = set()
            existing_isrcs = set()
            existing_names = set()

            if existing_pl:
                print("    Adding missing tracks only.")
                for t in existing_pl.tracks:
                    native = getattr(t, "spotify_id", None) or getattr(t, "video_id", None)
                    if native:
                        if target_id == "spotify" and not native.startswith("spotify:track:"):
                            native = f"spotify:track:{native}"
                        existing_ids.add(native)

                    if t.isrc:
                        existing_isrcs.add(t.isrc)
                    existing_names.add(f"{t.artist_name} - {t.title}".lower())

            new_ids = []
            for track, tid in zip(source.tracks, track_ids, strict=False):
                if not tid:
                    continue
                if tid in existing_ids:
                    continue
                if track.isrc and track.isrc in existing_isrcs:
                    continue
                name_key = f"{track.artist_name} - {track.title}".lower()
                if name_key in existing_names:
                    continue

                new_ids.append(tid)
                existing_ids.add(tid)
                if track.isrc:
                    existing_isrcs.add(track.isrc)
                existing_names.add(name_key)

            total_found = sum(1 for u in track_ids if u)
            skipped_count = total_found - len(new_ids)

            if skipped_count:
                print(f"⏩ Skipping {skipped_count} track(s) already in the playlist.")

            if new_ids:
                print(f"🚀 Adding {len(new_ids)} new track(s) to {target_id.title()}...")
                target_provider.add_tracks(playlist_id=dest_playlist_id, track_ids=new_ids)
            migrated_count = len(new_ids)

        # Upload cover image if supported by the provider
        if source.cover_url:
            if hasattr(target_provider, "upload_cover_image"):
                print(f"🖼️  Uploading playlist cover image to {target_id.title()}...")
                try:
                    target_provider.upload_cover_image(playlist_id=dest_playlist_id, image_url=source.cover_url)
                except Exception as err:
                    logger.warning("Failed to upload cover: %s", err)
            else:
                print(f"⚠️  Note: {target_id.title()} does not support custom playlist cover uploads via API.")

        result = MigrationResult(
            playlist_name=dest_name,
            target_playlist_id=dest_playlist_id,
            direction=direction_label,
            total_tracks=len(source.tracks),
            migrated_count=migrated_count,
            skipped_count=skipped_count,
            failed_tracks=failed,
        )
        self._print_summary(result)
        return result

    # ------------------------------------------------------------------
    # Internal helpers — search
    # ------------------------------------------------------------------

    @with_retries(max_retries=3, base_delay=1.0)
    async def _search_single(self, target_provider: MusicProvider, track: Track) -> str | None:
        return await asyncio.to_thread(target_provider.search_track, track)

    async def _search_tracks(
        self, target_provider: MusicProvider, tracks: list[Track]
    ) -> tuple[list[str], list[Track]]:
        total = len(tracks)
        tasks = [self._search_single(target_provider, track) for track in tracks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        track_ids: list[str] = []
        failed: list[Track] = []

        for idx, (track, result) in enumerate(zip(tracks, results, strict=False), start=1):
            if isinstance(result, Exception):
                print(f"  [{idx}/{total}] ❌ Error searching for {track.display_name}: {result}")
                track_ids.append("")
                failed.append(track)
            elif result:
                print(f"  [{idx}/{total}] ✅ Found: {track.display_name}")
                track_ids.append(result)
            else:
                print(f"  [{idx}/{total}] ❌ Not found: {track.display_name}")
                track_ids.append("")
                failed.append(track)
        return track_ids, failed

    def _resolve_playlist(
        self, target_provider: MusicProvider, name: str, source: Playlist, target_id: str
    ) -> tuple[str, Playlist | None]:
        existing = target_provider.get_existing_playlist(name)
        if existing:
            print(f"\n📋 Playlist '{name}' already exists on {target_id.title()} (ID: {existing.id}).")
            return existing.id, existing

        print(f"\n🔨 Creating {target_id.title()} playlist: '{name}'...")
        playlist_id = target_provider.create_playlist(
            title=name,
            description=f"Migrated from {source.source} playlist: {source.name}. {source.description}",
        )
        return playlist_id, None

    @staticmethod
    def _empty_result(name: str, direction_label: str) -> MigrationResult:
        return MigrationResult(
            playlist_name=name,
            target_playlist_id="",
            direction=direction_label,
            total_tracks=0,
            migrated_count=0,
            skipped_count=0,
            failed_tracks=[],
        )

    @staticmethod
    def _print_summary(result: MigrationResult) -> None:
        print("\n✨ Migration Summary:")
        print(f"  • Direction:         {result.direction}")
        print(f"  • Playlist Name:     {result.playlist_name}")
        print(f"  • Destination ID:    {result.target_playlist_id}")
        print(f"  • Tracks Added:      {result.migrated_count} (skipped {result.skipped_count} duplicates)")
        print(
            f"  • Success Rate:      {result.success_rate:.1f}% ({result.migrated_count + result.skipped_count}/{result.total_tracks})"
        )
        if result.failed_tracks:
            print(f"  • Unmatched ({len(result.failed_tracks)}):")
            for ft in result.failed_tracks:
                print(f"    - {ft.display_name}")
