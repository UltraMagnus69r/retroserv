"""Ask Cursor to match level layouts to course names. It does not edit the ROM or the reader."""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass

from .assistant import AssistantChange
from .assistant_settings import DEFAULT_MODEL, AssistantSettings, api_key


@dataclass(frozen=True)
class BrainDecision:
    names: dict[str, str]
    findings: tuple[AssistantChange, ...] = ()


class MatchError(ValueError):
    """Cursor ran, and the reply could not be used. `reply` is the raw text."""

    def __init__(self, message: str, *, reply: str = '', status: str = '', run_id: str = '', model: str = ''):
        super().__init__(message)
        self.reply = reply
        self.status = status
        self.run_id = run_id
        self.model = model


def cursor_requirement(settings: AssistantSettings, directory=None) -> str | None:
    """Why Cursor cannot run, or None when the key and the package are both present."""
    if settings.provider != 'cursor':
        return None
    if not api_key(directory):
        return ('Cursor needs an API key. Set it in File → Assistant settings, '
                'or export CURSOR_API_KEY.')
    try:
        import cursor_sdk  # noqa: F401
    except ImportError:
        return ('Cursor support is not installed for this Retroserv. '
                'From the Retroserv folder run: .venv/bin/pip install cursor-sdk')
    return None


def layout_brief(key, subject: str, image) -> dict:
    """A short column profile of one foreground. 0 is empty and 9 is solid."""
    from .map_match import signature
    samples = signature(image)
    width = 64
    digits = []
    for column in range(0, width, 2):
        values = [samples[row * width + column] for row in range(32)]
        digits.append(str(min(9, int(sum(values) / len(values) / 26))))
    screens = max(1, image.width // 256)
    return {'key': str(key), 'subject': subject, 'screens': screens, 'profile': ''.join(digits)}


def parse_match_response(text: str, allowed_titles: set[str], known_keys: set[str]) -> BrainDecision:
    """Accept only catalog titles, one room each. Drop anything else."""
    if not text.strip():
        raise ValueError('Cursor finished without a reply')
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('Cursor replied in prose instead of a JSON object')
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError('Cursor returned JSON that could not be read') from exc
    if not isinstance(payload, dict):
        raise ValueError('Cursor did not return a JSON object')
    names: dict[str, str] = {}
    used: set[str] = set()
    for item in payload.get('names') or []:
        if not isinstance(item, dict):
            continue
        key, title = str(item.get('key') or ''), str(item.get('title') or '').strip()
        if key not in known_keys or title not in allowed_titles or title in used or key in names:
            continue
        names[key] = title
        used.add(title)
    findings = []
    for item in payload.get('findings') or []:
        if not isinstance(item, dict):
            continue
        key, summary = str(item.get('key') or ''), str(item.get('summary') or '').strip()
        if key not in known_keys or not summary:
            continue
        findings.append(AssistantChange(
            f'cursor-finding-{key}', 'finding', summary[:240], key, {'provider': 'cursor'}))
    return BrainDecision(names, tuple(findings))


def _prompt(briefs: list[dict], titles: list[str]) -> str:
    catalog = '\n'.join(f'- {title}' for title in titles)
    levels = '\n'.join(json.dumps(brief, separators=(',', ':')) for brief in briefs)
    return (
        'Match these Super Mario World foreground layouts to course names from the catalog.\n'
        'Each profile is 32 digits: 0 is an empty column and 9 is a solid column.\n'
        'Reply with JSON only, no markdown, in this shape:\n'
        '{"names":[{"key":"room key","title":"exact catalog title"}],'
        '"findings":[{"key":"room key","summary":"one sentence about a visible glitch"}]}\n'
        'Omit a room when you are not sure. Use only catalog titles. '
        'Do not give one title to two rooms. Do not invent tile addresses or replacement colors. '
        'A finding is an observation. It is not a pixel edit.\n\n'
        f'Catalog:\n{catalog}\n\nLevels:\n{levels}\n'
    )


def ask_cursor_findings(report: str, settings: AssistantSettings, directory=None) -> BrainDecision:
    """One text-only look at a room report. Names in the reply are ignored."""
    problem = cursor_requirement(settings, directory)
    if problem:
        raise ValueError(problem)
    from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions
    message = (
        'Read this Super Mario World foreground report.\n'
        'Reply with JSON only, no markdown:\n'
        '{"names":[],"findings":[{"key":"room key from the report","summary":"one sentence"}]}\n'
        'Copy the key exactly. A finding is an observation. '
        'Do not invent palette numbers, tile addresses, or replacement colors.\n\n'
        f'{report}\n'
    )
    try:
        result = Agent.prompt(
            message,
            AgentOptions(
                api_key=api_key(directory),
                model=settings.model or DEFAULT_MODEL,
                tools=[],
                local=LocalAgentOptions(cwd=tempfile.mkdtemp(prefix='retroserv-cursor-')),
            ),
        )
    except CursorAgentError as exc:
        raise MatchError(f'Cursor did not start: {exc.message}', status='not-started') from exc
    reply = result.result or ''
    model = settings.model or DEFAULT_MODEL
    if result.status != 'finished':
        detail = result.error_message or result.status
        raise MatchError(f'Cursor stopped: {detail}', reply=reply, status=str(result.status),
                         run_id=result.id, model=model)
    key = report.split('key: ', 1)[-1].split('\n', 1)[0].strip()
    try:
        return parse_match_response(reply, set(), {key} if key else set())
    except ValueError as exc:
        raise MatchError(str(exc), reply=reply, status=str(result.status),
                         run_id=result.id, model=model) from exc


def ask_cursor(briefs: list[dict], titles: list[str], settings: AssistantSettings,
               directory=None) -> BrainDecision:
    """One Cursor run. The agent is pointed at an empty folder so it cannot edit this project."""
    problem = cursor_requirement(settings, directory)
    if problem:
        raise ValueError(problem)
    from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions
    try:
        result = Agent.prompt(
            _prompt(briefs, titles),
            AgentOptions(
                api_key=api_key(directory),
                model=settings.model or DEFAULT_MODEL,
                tools=[],
                local=LocalAgentOptions(cwd=tempfile.mkdtemp(prefix='retroserv-cursor-')),
            ),
        )
    except CursorAgentError as exc:
        raise MatchError(f'Cursor did not start: {exc.message}', status='not-started') from exc
    reply = result.result or ''
    model = settings.model or DEFAULT_MODEL
    if result.status != 'finished':
        detail = result.error_message or result.status
        raise MatchError(f'Cursor stopped: {detail}', reply=reply, status=str(result.status),
                         run_id=result.id, model=model)
    try:
        return parse_match_response(reply, set(titles), {brief['key'] for brief in briefs})
    except ValueError as exc:
        raise MatchError(str(exc), reply=reply, status=str(result.status),
                         run_id=result.id, model=model) from exc
