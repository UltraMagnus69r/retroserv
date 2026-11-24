"""Fedora Workstation native and Atomic/Distrobox launcher contracts.

Host install and container operations are intentionally mocked. Running the
real installer is a separate acceptance test on supported Fedora machines.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def copy_launchers(tmp_path: Path) -> Path:
    project = tmp_path / 'home' / 'source with spaces'
    project.mkdir(parents=True)
    for script in ROOT.glob('*.sh'):
        shutil.copy2(script, project / script.name)
    shutil.copytree(ROOT / 'scripts', project / 'scripts')
    return project


def fake_bin(tmp_path: Path) -> Path:
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    for name in ('distrobox',):
        script = bindir / name
        script.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
        script.chmod(0o755)
    return bindir


def env_for(tmp_path: Path, mode: str, bindir: Path | None = None) -> dict:
    env = os.environ.copy()
    env.update(HOME=str(tmp_path / 'home'), RETROSERV_MODE=mode)
    if bindir:
        env['PATH'] = f'{bindir}:{env["PATH"]}'
    return env


@pytest.mark.skipif(shutil.which('bash') is None, reason='requires bash')
def test_fedora_launchers_have_valid_shell_syntax_and_execute_bit():
    paths = sorted(ROOT.glob('*.sh')) + sorted((ROOT / 'scripts').glob('*.sh'))
    assert len(paths) >= 10
    result = subprocess.run(['bash', '-n', *(str(p) for p in paths)], capture_output=True)
    assert result.returncode == 0, result.stderr
    assert all(p.stat().st_mode & 0o100 for p in paths)


@pytest.mark.skipif(shutil.which('bash') is None, reason='requires bash')
@pytest.mark.parametrize(('launcher', 'args', 'expected'), [
    ('Start-Retroserv.sh', [], ['-m', 'retroserv', 'gui']),
    ('Retroserv-CLI.sh', ['inspect', 'hello world.sfc'], ['-m', 'retroserv', 'inspect', 'hello world.sfc']),
    ('Run-Retroserv-MCP.sh', [], ['-m', 'retroserv.mcp_server']),
    ('Install-MCP.sh', [], ['-m', 'pip', 'install']),
])
def test_native_fedora_launchers_forward_correct_commands(tmp_path, launcher, args, expected):
    project = copy_launchers(tmp_path)
    python = project / '.venv' / 'bin' / 'python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    python.chmod(0o755)
    result = subprocess.run([str(project / launcher), *args], text=True, capture_output=True,
                            env=env_for(tmp_path, 'native'), check=True)
    tokens = result.stdout.splitlines()
    assert tokens[:len(expected)] == expected
    if launcher == 'Install-MCP.sh':
        assert tokens[4].endswith('[mcp]')


@pytest.mark.skipif(shutil.which('bash') is None, reason='requires bash')
@pytest.mark.parametrize(('launcher', 'args', 'expected_tail'), [
    ('Start-Retroserv.sh', [], ['gui']),
    ('Retroserv-CLI.sh', ['inspect', 'hello world.sfc'], ['inspect', 'hello world.sfc']),
    ('Run-Retroserv-MCP.sh', [], []),
    ('Install-MCP.sh', [], []),
])
def test_atomic_fedora_launchers_forward_correct_commands(tmp_path, launcher, args, expected_tail):
    project = copy_launchers(tmp_path)
    bindir = fake_bin(tmp_path)
    result = subprocess.run([str(project / launcher), *args], text=True, capture_output=True,
                            env=env_for(tmp_path, 'distrobox', bindir), check=True)
    tokens = result.stdout.splitlines()
    assert tokens[:6] == ['enter', '--no-tty', '--name', 'retroserv-dev', '--', 'bash']
    assert str(project) in tokens
    if expected_tail:
        assert tokens[-len(expected_tail):] == expected_tail
    else:
        assert tokens[-2].endswith('-in-box.sh')


def test_setup_check_is_non_mutating_and_detects_override(tmp_path):
    project = copy_launchers(tmp_path)
    result = subprocess.run([str(project / 'Setup-Fedora.sh'), '--check'], capture_output=True,
                            text=True, env=env_for(tmp_path, 'native'), check=True)
    assert 'Installation mode: native' in result.stdout
    assert not (project / '.retroserv-install-mode').exists()
    result = subprocess.run([str(project / 'Setup-Fedora.sh'), '--check'], capture_output=True,
                            text=True, env=env_for(tmp_path, 'distrobox'), check=True)
    assert 'Installation mode: distrobox' in result.stdout
    assert not (project / '.retroserv-install-mode').exists()


def test_saved_mode_is_used_when_no_override(tmp_path):
    project = copy_launchers(tmp_path)
    (project / '.retroserv-install-mode').write_text('distrobox\n')
    bindir = fake_bin(tmp_path)
    env = env_for(tmp_path, 'distrobox', bindir)
    env.pop('RETROSERV_MODE')
    result = subprocess.run([str(project / 'Retroserv-CLI.sh'), '--version'], capture_output=True,
                            text=True, env=env, check=True)
    assert result.stdout.startswith('enter\n')


def test_missing_native_environment_prints_setup_hint(tmp_path):
    project = copy_launchers(tmp_path)
    result = subprocess.run([str(project / 'Start-Retroserv.sh')], capture_output=True,
                            text=True, env=env_for(tmp_path, 'native'))
    assert result.returncode != 0
    assert 'Setup-Fedora.sh' in result.stderr


def test_old_windows_launchers_removed():
    assert not (ROOT / 'Start-Retroserv.bat').exists()
    assert not (ROOT / 'Build-Windows.ps1').exists()
