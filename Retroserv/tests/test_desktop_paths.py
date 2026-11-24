"""ROM dialog starts at Fedora Desktop rather than the working directory."""
from pathlib import Path

from retroserv.desktop_paths import default_rom_directory


def test_standard_fedora_desktop(tmp_path: Path):
    desktop = tmp_path / 'Desktop'
    desktop.mkdir()
    assert default_rom_directory(home=tmp_path, config_home=tmp_path / '.config') == desktop


def test_xdg_redirected_desktop_with_spaces(tmp_path: Path):
    desktop = tmp_path / 'My Desktop'
    desktop.mkdir()
    config = tmp_path / '.config'
    config.mkdir()
    (config / 'user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME/My Desktop"\n')
    assert default_rom_directory(home=tmp_path, config_home=config) == desktop


def test_xdg_disabled_desktop_points_to_home(tmp_path: Path):
    desktop = tmp_path / 'Desktop'
    desktop.mkdir()
    config = tmp_path / '.config'
    config.mkdir()
    (config / 'user-dirs.dirs').write_text('XDG_DESKTOP_DIR="${HOME}"\n')
    assert default_rom_directory(home=tmp_path, config_home=config) == tmp_path


def test_missing_desktop_falls_back_to_home(tmp_path: Path):
    assert default_rom_directory(home=tmp_path, config_home=tmp_path / '.config') == tmp_path


def test_nonexistent_xdg_path_falls_back_to_standard_desktop(tmp_path: Path):
    desktop = tmp_path / 'Desktop'
    desktop.mkdir()
    config = tmp_path / '.config'
    config.mkdir()
    (config / 'user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME/Missing Desktop"\n')
    assert default_rom_directory(home=tmp_path, config_home=config) == desktop


def test_no_shell_interpretation_of_xdg_config(tmp_path: Path):
    config = tmp_path / '.config'
    config.mkdir()
    (config / 'user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$(touch bad-file)"\n')
    assert default_rom_directory(home=tmp_path, config_home=config) == tmp_path
    assert not (tmp_path / 'bad-file').exists()


def test_open_rom_passes_initial_directory_to_dialog(tmp_path, monkeypatch):
    """Verify the actual GUI method's file dialog receives the default location."""
    from retroserv import gui

    desktop = tmp_path / 'Desktop'
    desktop.mkdir()
    called = {}

    def fake_dialog(**kwargs):
        called.update(kwargs)
        return ''  # User cancelled; no live Tk window required.

    monkeypatch.setattr(gui, 'default_rom_directory', lambda: desktop)
    monkeypatch.setattr(gui.filedialog, 'askopenfilename', fake_dialog)

    class Idle:
        _checking = False

    gui.RetroservGUI.open_rom(Idle())
    assert called['initialdir'] == str(desktop)
    assert called['title'] == 'Select SNES ROM'
