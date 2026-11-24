
// Read-only probe for the Retroserv foreground comparison.
extern "C" const void *retro_reference_memory(unsigned region)
{
    if (region == 0) return Memory.RAM;
    if (region == 1) return Memory.VRAM;
    if (region == 2) return PPU.CGDATA;
    if (region == 3) return &PPU.BG[0];
    return nullptr;
}
