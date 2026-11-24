#!/usr/bin/env bash
# Shared Fedora host/container selection. ROOT must be set by caller.
set -Eeuo pipefail

retroserv_mode() {
  local mode="${RETROSERV_MODE:-auto}"
  if [[ "$mode" == auto && -f "$ROOT/.retroserv-install-mode" ]]; then
    mode="$(<"$ROOT/.retroserv-install-mode")"
  fi
  if [[ "$mode" == auto ]]; then
    if [[ -e /run/ostree-booted ]] || [[ -e /run/bootc-booted ]]; then
      mode=distrobox
    else
      mode=native
    fi
  fi
  case "$mode" in
    native|distrobox) printf '%s\n' "$mode" ;;
    *) echo "ERROR: Invalid RETROSERV_MODE='$mode' (expected native, distrobox or auto)." >&2; return 2 ;;
  esac
}

retroserv_require_home() {
  # Distrobox must be able to access the project through the shared home mount.
  case "$ROOT/" in
    "$HOME/"*) ;;
    *) echo "ERROR: For Distrobox, extract Retroserv beneath $HOME (currently: $ROOT)." >&2; return 2 ;;
  esac
}
