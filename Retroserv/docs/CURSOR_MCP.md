# Cursor MCP configuration — Fedora Linux

After running `./Setup-Fedora.sh` (both native and Distrobox modes):

```bash
./Install-MCP.sh
```

Configure Cursor's `~/.cursor/mcp.json` with an additional `mcpServers.retroserv`
entry. Example for a Fedora laptop where your account name is `user`:

```json
{
  "mcpServers": {
    "retroserv": {
      "command": "/home/user/Retroserv/Run-Retroserv-MCP.sh"
    }
  }
}
```

Replace `/home/user/Retroserv` with the **actual full path** printed by
`realpath ./Run-Retroserv-MCP.sh`; on Bazzite it may start with `/var/home/`.
If Cursor already has servers, **merge** the `retroserv` entry; do not
replace the whole file.

The wrapper selects native Python for standard Fedora or Fedora Distrobox for
Atomic systems based on your successful setup. It speaks **stdio**, not HTTP.
Provided methods: inspect_rom, find_graphics_candidates, find_ascii_strings,
export_graphics, export_raw_region, list_smw_gfx, export_smw_gfx, inspect_smw_level.

The recovery build was checked with a local stdio client on Fedora. Cursor integration has not been checked.
The source ROM remains untouched; exports write explicit output paths. A
client with access to these tools can read files Retroserv can read, so only
connect trusted local clients.
