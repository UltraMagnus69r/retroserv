"""Compare every horizontal SMW room with every course map on a page the user names."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from .access_paths import data_directory
from .assistant import AssistantFile, AssistantRoom, merge_assistant
from .cursor_match import BrainDecision, layout_brief
from .map_match import MapScore, assign_matches, signature
from .map_source import course_maps
from .smw_foreground import render_opening_foreground
from .smw_level import level_catalog


@dataclass(frozen=True)
class CheckProgress:
    """One step of a map check. `total` is the level count; 0 means the levels have not started."""

    message: str
    completed: int = 0
    total: int = 0


def _decision(decide, briefs, pictures, level_count, progress) -> BrainDecision | None:
    if decide is None:
        return None
    progress(CheckProgress('Asking Cursor to match the levels', level_count, level_count))
    decision = decide(briefs, [picture.title for picture in pictures])
    if not isinstance(decision, BrainDecision):
        raise ValueError('The assistant did not return a match decision')
    return decision


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={'User-Agent': 'Retroserv'})
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError(f'Could not read {url}') from exc


def default_map_cache() -> Path:
    return data_directory() / 'map-cache'


def map_signature(url: str, fetch, folder: Path | None = None, retrieve=None):
    """Grayscale signature for one map image.

    A second look at the same address reuses the stored signature when the
    server answers that the image has not changed. An injected `fetch` is never
    cached, so tests stay on the bytes they pass in.
    """
    cached, etag = _cached_signature(folder, url)
    getter = retrieve if retrieve is not None else (_conditional_get if fetch is fetch_bytes and folder is not None else None)
    if getter is None:
        body = fetch(url)
        new_etag = ''
        status = 200
    else:
        status, body, new_etag = getter(url, etag)
        if status == 304 and cached is not None:
            return cached
        if status == 304:
            status, body, new_etag = getter(url, '')
    image = Image.open(BytesIO(body))
    try:
        found = signature(image)
    finally:
        image.close()
    if folder is not None and getter is not None:
        _store_signature(folder, url, new_etag or etag, found)
    return found


def _conditional_get(url: str, etag: str) -> tuple[int, bytes, str]:
    headers = {'User-Agent': 'Retroserv'}
    if etag:
        headers['If-None-Match'] = etag
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            status = getattr(response, 'status', 200)
            new_etag = response.headers.get('ETag', '') if getattr(response, 'headers', None) else ''
            if status == 304:
                return 304, b'', etag
            return status, response.read(), new_etag
    except HTTPError as exc:
        if exc.code == 304:
            return 304, b'', etag
        raise ValueError(f'Could not read {url}') from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError(f'Could not read {url}') from exc


def _cache_key(url: str) -> str:
    return sha256(url.encode()).hexdigest()


def _cached_signature(folder: Path | None, url: str) -> tuple[tuple[int, ...] | None, str]:
    if folder is None:
        return None, ''
    key = _cache_key(url)
    signature_path = folder / f'{key}.sig'
    meta_path = folder / f'{key}.json'
    if not signature_path.is_file():
        return None, ''
    try:
        stored = tuple(signature_path.read_bytes())
        meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.is_file() else {}
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None, ''
    etag = meta.get('etag') if isinstance(meta, dict) else ''
    return stored, etag if isinstance(etag, str) else ''


def _store_signature(folder: Path, url: str, etag: str, found: tuple[int, ...]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url)
    signature_path = folder / f'{key}.sig'
    meta_path = folder / f'{key}.json'
    temporary = folder / f'{key}.sig.tmp'
    temporary.write_bytes(bytes(found))
    os.replace(temporary, signature_path)
    meta_path.write_text(json.dumps({'url': url, 'etag': etag}) + '\n', encoding='utf-8')


def check_course_maps(rom, source_url: str, assistant: AssistantFile | None = None,
                      progress=lambda _update: None, *, fetch=fetch_bytes,
                      rooms_for=level_catalog, render=render_opening_foreground,
                      decide=None, cache_dir: Path | None = None,
                      cache_enabled: bool | None = None) -> AssistantFile:
    """Walk every room and every course map. Name a room only on a unique match."""
    enabled = fetch is fetch_bytes if cache_enabled is None else cache_enabled
    folder = (cache_dir if cache_dir is not None else default_map_cache()) if enabled else None
    progress(CheckProgress('Reading the map page'))
    page = fetch(source_url)
    maps = course_maps(page.decode('utf-8', errors='replace'), source_url)
    if not maps:
        raise ValueError('That page has no course-map images')
    pictures: list[MapScore] = []
    for index, course in enumerate(maps, start=1):
        progress(CheckProgress(f'Map {index} of {len(maps)} · {course.title}'))
        try:
            pictures.append(MapScore(course.title, course.url, map_signature(course.url, fetch, folder)))
        except (OSError, ValueError):
            continue
    if not pictures:
        raise ValueError('None of the course maps on that page could be read')
    catalog = list(rooms_for(rom))
    level_count = len(catalog)
    levels: dict[str, tuple[int, ...]] = {}
    subjects: dict[str, str] = {}
    briefs = []
    for index, (label, key) in enumerate(catalog, start=1):
        ident = label.split('  ', 1)[0]
        progress(CheckProgress(f'Level {index} of {level_count} · {ident}', index - 1, level_count))
        subjects[str(key)] = ident
        try:
            rendered = render(rom, key, assistant)
            levels[str(key)] = signature(rendered.image)
            briefs.append(layout_brief(key, ident, rendered.image))
        except (OSError, ValueError):
            pass
        progress(CheckProgress(f'Level {index} of {level_count} · {ident}', index, level_count))
    decision = _decision(decide, briefs, pictures, level_count, progress)
    progress(CheckProgress('Comparing every level with every map', level_count, level_count))
    matched = assign_matches(levels, tuple(pictures))
    title_urls = {picture.title: picture.url for picture in pictures}
    claimed: set[str] = set()
    rooms = {}
    for key, subject in subjects.items():
        title, url, candidates = matched.get(key, (None, None, ()))
        if decision is not None:
            title, url = None, None
            chosen = decision.names.get(key)
            if chosen and chosen in title_urls and chosen not in claimed:
                title, url = chosen, title_urls[chosen]
                claimed.add(chosen)
        rooms[key] = AssistantRoom(subject, title, url, candidates)
    sha = sha256(rom.data).hexdigest() if rom is not None else (assistant.rom_sha256 if assistant else '')
    prior = tuple(change for change in (assistant.changes if assistant else ())
                  if not change.id.startswith('cursor-finding-'))
    findings = decision.findings if decision is not None else ()
    report = AssistantFile(sha, source_url, len(pictures), rooms, prior + findings)
    merged = merge_assistant(assistant, report)
    if findings or (assistant and any(change.id.startswith('cursor-finding-') for change in assistant.changes)):
        kept = tuple(change for change in merged.changes if not change.id.startswith('cursor-finding-'))
        merged = AssistantFile(merged.rom_sha256, merged.source, merged.source_map_count,
                               merged.rooms, kept + findings)
    named = sum(room.title is not None for room in merged.rooms.values())
    progress(CheckProgress(
        f'Named {named} of {len(merged.rooms)} levels from {len(pictures)} maps',
        level_count, level_count))
    return merged
