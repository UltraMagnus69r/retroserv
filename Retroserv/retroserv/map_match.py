"""Compare a rendered room with course-map pictures.

A title is accepted only when this room's picture is close to one map, far
from the other maps, and no other room is equally close to that same map.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .assistant import AssistantCandidate

MINIMUM = 0.92
MARGIN = 0.08
_GRID = (64, 32)


@dataclass(frozen=True)
class MapScore:
    title: str
    url: str
    signature: tuple[int, ...]


def signature(image: Image.Image) -> tuple[int, ...]:
    gray = image.convert('L').resize(_GRID, Image.Resampling.BOX)
    return tuple(gray.tobytes())


def similarity(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    count = len(left)
    mean_left = sum(left) / count
    mean_right = sum(right) / count
    numerator = 0.0
    left_energy = 0.0
    right_energy = 0.0
    for a, b in zip(left, right):
        da = a - mean_left
        db = b - mean_right
        numerator += da * db
        left_energy += da * da
        right_energy += db * db
    if left_energy == 0 or right_energy == 0:
        return 1.0 if left_energy == right_energy == 0 and abs(mean_left - mean_right) < 1 else 0.0
    return numerator / (left_energy ** 0.5 * right_energy ** 0.5)


def assign_matches(level_signatures: dict[str, tuple[int, ...]],
                   maps: tuple[MapScore, ...]) -> dict[str, tuple[str | None, str | None, tuple[AssistantCandidate, ...]]]:
    """Return room key -> (title or None, map url or None, closest candidates)."""
    scores: dict[str, list[AssistantCandidate]] = {}
    best_for_map: dict[str, list[tuple[float, str]]] = {item.url: [] for item in maps}
    for key, level in level_signatures.items():
        ranked = [AssistantCandidate(item.title, item.url, similarity(level, item.signature))
                  for item in maps]
        ranked.sort(key=lambda candidate: candidate.score, reverse=True)
        scores[key] = ranked
        for candidate in ranked:
            best_for_map[candidate.url].append((candidate.score, key))
    chosen = {}
    for key, ranked in scores.items():
        title, url = _accept(key, ranked, best_for_map)
        chosen[key] = (title, url, tuple(ranked[:3]))
    return chosen


def _accept(key: str, ranked: list[AssistantCandidate],
            best_for_map: dict[str, list[tuple[float, str]]]) -> tuple[str | None, str | None]:
    if not ranked or ranked[0].score < MINIMUM:
        return None, None
    second = ranked[1].score if len(ranked) > 1 else 0.0
    if ranked[0].score - second < MARGIN:
        return None, None
    contenders = sorted(best_for_map[ranked[0].url], reverse=True)
    if not contenders or contenders[0][1] != key:
        return None, None
    other = contenders[1][0] if len(contenders) > 1 else 0.0
    if contenders[0][0] - other < MARGIN:
        return None, None
    return ranked[0].title, ranked[0].url
