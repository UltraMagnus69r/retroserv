"""Check maps and rebuild rooms away from the window class."""
from __future__ import annotations

from .assistant_settings import AssistantSettings
from .cursor_match import ask_cursor, ask_cursor_findings, cursor_requirement
from .error_log import write_error_log
from .map_source import DEFAULT_MAP_PAGE, course_maps
from .smw_map_check import CheckProgress, check_course_maps, fetch_bytes
from .smw_rebuild import foreground_report, rebuild_from_rom


def run_map_check(rom, url: str, assistant, settings: AssistantSettings, progress):
    """Name rooms from course-map pictures, optionally asking Cursor."""
    decide = None
    if settings.provider == 'cursor':
        decide = lambda briefs, titles: ask_cursor(briefs, titles, settings)
    return check_course_maps(rom, url, assistant, progress, decide=decide)


def run_rebuild(rom, assistant, settings: AssistantSettings, progress):
    """Name rooms from the overworld. Returns the file and a Cursor note, if any."""
    url = assistant.source if assistant and assistant.source else DEFAULT_MAP_PAGE
    try:
        page = fetch_bytes(url).decode('utf-8', errors='replace')
        maps = course_maps(page, url)
    except (OSError, ValueError):
        maps = ()
    result = rebuild_from_rom(rom, assistant, maps, progress, screenshot_folder=settings.screenshot_folder)
    note = ''
    if settings.provider == 'cursor' and cursor_requirement(settings) is None:
        progress(CheckProgress('Asking Cursor about the foreground', 2, 2))
        try:
            decision = ask_cursor_findings(
                foreground_report(rom, screenshot_folder=settings.screenshot_folder), settings)
            result = rebuild_from_rom(
                rom, result, maps, findings=decision.findings,
                screenshot_folder=settings.screenshot_folder)
        except (OSError, ValueError, RuntimeError) as exc:
            note = str(exc)
            write_error_log(exc, context='Foreground look')
    return result, note
