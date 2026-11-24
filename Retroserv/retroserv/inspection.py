"""Game-neutral inspection snapshot.

A game module fills this in. The desktop view, CLI, and MCP read it and do not
need that game's level types. Record labels, captions, and grid guides are
display text supplied by the game.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

FORMAT = 'retroserv-inspection-v1'


@dataclass(frozen=True)
class InspectionRecord:
    id: str
    label: str
    detail: str
    offset: int
    raw_hex: str

    def to_dict(self) -> dict:
        return {'id': self.id, 'label': self.label, 'detail': self.detail,
                'offset': self.offset, 'raw_hex': self.raw_hex}


@dataclass(frozen=True)
class InspectionMarker:
    record_id: str
    x: int
    y: int
    shape: str

    def to_dict(self) -> dict:
        return {'record_id': self.record_id, 'x': self.x, 'y': self.y, 'shape': self.shape}


@dataclass(frozen=True)
class InspectionGuide:
    x: int
    label: str

    def to_dict(self) -> dict:
        return {'x': self.x, 'label': self.label}


@dataclass(frozen=True)
class InspectionCell:
    record_id: str
    caption: str


@dataclass(frozen=True)
class InspectionSurface:
    image: Image.Image
    cell_pixels: int
    columns: int
    rows: int
    cells: dict[tuple[int, int], InspectionCell]

    def to_dict(self) -> dict:
        cells = [{'x': x, 'y': y, 'record_id': cell.record_id, 'caption': cell.caption}
                 for (x, y), cell in sorted(self.cells.items(), key=lambda item: (item[0][1], item[0][0]))]
        return {'width': self.image.width, 'height': self.image.height,
                'cell_pixels': self.cell_pixels, 'columns': self.columns, 'rows': self.rows,
                'cells': cells}


@dataclass(frozen=True)
class InspectionSnapshot:
    format: str
    platform: str
    game: str
    subject: str
    name: str
    cartridge_sha256: str
    source_name: str
    copier_header_size: int
    summary: str
    legend: str
    export_name: str
    grid_columns: int
    grid_rows: int
    screen_columns: int
    supports_surface: bool
    guides: tuple[InspectionGuide, ...]
    records: tuple[InspectionRecord, ...]
    markers: tuple[InspectionMarker, ...]
    surface: InspectionSurface | None

    def to_dict(self) -> dict:
        return {
            'format': self.format,
            'platform': self.platform,
            'game': self.game,
            'subject': self.subject,
            'name': self.name,
            'cartridge_sha256': self.cartridge_sha256,
            'source_name': self.source_name,
            'copier_header_size': self.copier_header_size,
            'summary': self.summary,
            'legend': self.legend,
            'grid_columns': self.grid_columns,
            'grid_rows': self.grid_rows,
            'screen_columns': self.screen_columns,
            'supports_surface': self.supports_surface,
            'guides': [guide.to_dict() for guide in self.guides],
            'records': [record.to_dict() for record in self.records],
            'markers': [marker.to_dict() for marker in self.markers],
            'surface': None if self.surface is None else self.surface.to_dict(),
        }
