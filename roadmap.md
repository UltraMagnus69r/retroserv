# Retroserv roadmap

## Stated goals

- Build a preservation workbench that can inspect ROMs, extract assets, and reconstruct levels from the original game data.
- Support selected **SNES and NES games**. Start with Super Mario World on SNES and use one NES game to test what can be shared.
- Build a **level editor** that can change terrain, objects, and sprite placements. Preserve links to the original records so changes can be understood, undone, and eventually exported.
- Produce playable changes through patches or separate ROM copies and verify them in an emulator.
- Bring Retroserv into another project once the destination and its interfaces are known.
- Keep the Fedora desktop app, CLI, and local MCP usable as the project grows. Verify the Bazzite setup on a live system.

## Current baseline

Retroserv can inspect SNES ROMs and extract vanilla Super Mario World graphics with palette and source provenance. It can show placement records for Yoshi’s Island 1 ($105) and its bonus room ($1CB). The opening foreground of $105 matches all 432 Map16 cells and the isolated foreground pixels loaded by Snes9x 1.63. Clicking a rendered tile selects the last object that wrote it. The handoff snapshot passed 49 tests.

NES decoding, level editing, playable exports, and integration into the destination project are still open. See [the Cursor handoff](CURSOR-HANDOFF.md) for setup, project history, and verification commands.

## 1. Add the first NES game

**Next decision:** Choose one game, one known ROM revision, and one opening screen. Favor a game with a verified local ROM, documented level data, and an emulator reference.

- Implement a game adapter that identifies the cartridge revision and reads the level records, tile graphics, and palettes it needs.
- Preserve ordered source records, offsets, raw bytes, and ROM identity.
- Show placements and render the opening screen in the viewer. Connect a tile click to the source record that drew it.

**Done when:** The opening screen matches an emulator reference and tile selection works on both the NES example and the existing SNES example.

## 2. Share the viewer and expand SMW reconstruction

- Use the two adapters to identify the viewer behavior they share. Extract scrolling, zoom, selection, and tile hit-testing. Keep level decoding, object expansion, graphics, and palette rules in each game adapter.
- Expand the Yoshi’s Island 1 foreground in verified batches. Check object order, overlaps, and cross-screen writes. Compare Map16 IDs before comparing pixels.
- Reconstruct the bonus room, entrance and exit links, backgrounds, and animated tiles. Resolve the correct palette from game data where the context is known.
- Turn sprite records into visible sprites and animations. Keep their rendered appearance linked to the underlying placements.

**Done when:** Both rooms can be inspected as a connected level and each supported visual layer has an emulator reference.

## 3. Build the first level editor

- Keep imported source records separate from editable state. Start with moving an object and resizing a ledge.
- Re-render after each change and implement undo and redo. Save an editable project with a schema version and the source ROM fingerprint.
- Add supported object and sprite insertion, deletion, and property editing. Validate edits against each game’s constraints.
- Exercise the shared editor interactions with both the SNES and NES examples.

**Done when:** A user can make, undo, save, and reopen an edit, and the reopened project renders the same result.

## 4. Export playable changes

- Prove that decoding and re-encoding an unchanged supported level reproduces its original bytes.
- Export one simple edit as a patch or separate ROM copy. Load it in an emulator and confirm the change is playable.
- Expand export support to handle larger streams, pointer relocation, exits, and any checksums required by the game. Add regression tests for unchanged regions and invalid edits.

**Done when:** The original ROM stays byte-identical and each supported game has a repeatable export and emulator test.

## 5. Integrate into the destination project

- Identify the target project and review its data model, UI, and existing NES or SNES tooling. This review can start as soon as the target is known.
- Decide which decoder, renderer, editor, and export interfaces to move or share. Keep the standalone app runnable during integration.
- Carry over the existing ROM provenance, tests, and emulator references.

**Done when:** The destination project can open the verified SNES and NES screens, show their source links, and reproduce the supported editing and export workflow.

## 6. Extend preservation tooling

- Add disassembly and emulator-debugging workflows for tracing unknown game behavior.
- Trace one known music cue, sound effect, or dialogue message at a time. Build game-specific exporters after the decoded result can be checked.
- Revisit playable custom level creation after editing and export are reliable.

**Done when:** Each added decoder has a verified example, source provenance, and a repeatable test.

## Release checks

Keep the ROM read-only during inspection and rendering. Run the existing regression suite and verify relevant GUI, CLI, and MCP paths as features land. Keep native Fedora setup working and record live Bazzite and Cursor MCP verification separately. Use [the emulator verification scripts](verification/) as the starting point for future visual comparisons.
