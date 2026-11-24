"""Read a page of labeled course-map images. World maps and archives are skipped."""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

DEFAULT_MAP_PAGE = 'https://www.mariouniverse.com/maps-snes-smw/'


@dataclass(frozen=True)
class CourseMap:
    title: str
    url: str


class _Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self._href = dict(attrs).get('href')
            self._parts = []

    def handle_endtag(self, tag):
        if tag == 'a' and self._href:
            title = ' '.join(''.join(self._parts).split())
            self.links.append((self._href, title))
            self._href = None

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)


def course_maps(html: str, page_url: str) -> tuple[CourseMap, ...]:
    """Labeled PNG and JPEG links on a map index. One entry per image."""
    parser = _Anchors()
    parser.feed(html)
    found: list[CourseMap] = []
    seen: set[str] = set()
    for href, title in parser.links:
        url = urljoin(page_url, href)
        path = urlparse(url).path.lower()
        if 'world-map' in path or not path.endswith(('.png', '.jpg', '.jpeg')):
            continue
        if not title or title.lower().startswith('world map'):
            continue
        if url in seen:
            continue
        seen.add(url)
        found.append(CourseMap(title.replace('’', "'").replace('‘', "'"), url))
    return tuple(found)
