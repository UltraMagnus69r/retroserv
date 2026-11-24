# Verified open-source ecosystem / integration candidates

Retroserv 0.1.2 is originally authored Python code with runtime dependency on Pillow. This list is integration research; **listing does not imply implementation or bundling.** Before linking, redistributing, or copying any code, review the applicable license and attribution requirements.

| Project | Role | License (as publicly stated) | Status in 0.1.2 |
|---|---|---|---|
| [SNESdev ROM header guide](https://snes.nesdev.org/wiki/ROM_header) | Hardware specification for internal headers and checksums | Documentation (check site terms) | Consulted, not copied |
| [SNESdev ROM formats](https://snes.nesdev.org/wiki/ROM_file_formats) | Copier header, ROM layout | Documentation (check site terms) | Consulted, not copied |
| [SuperFamiconv](https://github.com/Optiroc/SuperFamiconv) | Convert tiles, palettes and tilemaps to SNES formats | MIT | Future external-tool adapter; not installed |
| [MesenCE](https://github.com/nesdev-org/MesenCE) | SNES emulator, debugger, SPC dumper | GPL-3.0 | Future debug trace/manual export interoperability; not installed |
| [Ghidra SNES](https://github.com/joshleaves/ghidra-snes) | 65816 disassembly and SNES ROM loading in Ghidra | MIT (repository) | Future external integration; not installed |
| [Ghidra](https://github.com/NationalSecurityAgency/ghidra) | General reverse engineering platform | Apache-2.0 | Future external integration; not installed |
| [PVSnesLib](https://github.com/alekmaul/pvsneslib) | Compile new SNES homebrew | Permissive pvsneslib_license.txt, verify bundled subtools separately | Future build/export adapter; not installed |
| [GBSNES Studio](https://github.com/alekmaul/gbsnes-studio) | Game authoring reference using PVSnesLib | MIT for stated project portions; verify bundled subcomponents | Future reference; not installed |
| [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) | MCP stdio bridge | MIT | Optional pip dependency and implemented adapter (handshake untested here) |
| [Pillow](https://github.com/python-pillow/Pillow) | PNG output and Tk preview | HPND | Runtime dependency |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | Optional standalone executable packaging | GPL with special exception (see project) | No standalone binary provided; not integrated |

## License separation

MesenCE and other GPL components should be integrated first by external process, trace import, or documented file interoperability rather than copying source into Retroserv. Compatibility depends on actual architecture and redistribution details. External tool versions should be pinned and verified before shipping integrations.

## Architecture proposals for later versions

- `adapters/mesen/`: consume debugger-produced memory snapshots or trace exports. Do not claim a live MesenCE API until verified.
- `adapters/superfamiconv/`: optional subprocess wrapper for round-trip conversion.
- `adapters/ghidra/`: generate import metadata, no implied automatic disassembly correctness.
- `adapters/pvsneslib/`: export new source project **from independently authored content or properly licensed assets**, never a promise to compile extracted foreign code automatically.
- `plugins/compression/`: game-specific offset and codec configuration with reproducible provenance.


## Implemented in Retroserv 0.2 alpha
- Original, auditable Python implementation of LC_LZ2 from public format specifications
  (SnesLab and SMW-Editor). No copyrighted game data distributed.
- Version-gated SMW USA v1.0 GFX pointer profile using community-documented
  SNES addresses $00B992 / $00B9C4 / $00B9F6.
- Native 3bpp graphics decoding with provenance sidecars.

These implementations do not vendor or bundle external tools; known projects
remain references and optional future interoperability targets.
