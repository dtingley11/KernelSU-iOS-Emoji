#include "library_maps.h"
#include <cassert>
#include <initializer_list>

using namespace clash_font;

int main() {
    // The two actual library copies from the failed OnePlus trial. The hook
    // originally reached only the second copy, despite a shared file identity.
    LibraryMap maps[6]{};
    assert(parse_library_map("799fc73000-799fc96000 r-xp 00021000 fe:18 29840135 /system/lib64/libandroid.so\n", maps[0]));
    assert(parse_library_map("7ab155d000-7ab155e000 r-xp 00021000 fe:18 29840135 /system/lib64/libandroid.so\n", maps[1]));
    assert(parse_library_map("7ab155e000-7ab1580000 r-xp 00022000 fe:18 29840135 /system/lib64/libandroid.so\n", maps[2]));
    AssetTargets targets;
    assert(select_asset_targets(maps, 3, 0x7ab155dff0, targets));
    assert(targets.count == 2);
    assert(targets.addresses[0] == 0x799fc73ff0);
    assert(targets.addresses[1] == 0x7ab155dff0);
    assert(select_asset_targets(maps, 1, 0x799fc73ff0, targets));
    assert(targets.count == 1 && targets.addresses[0] == 0x799fc73ff0);
    assert(!select_asset_targets(maps, 3, 0x799fc97000, targets));
    assert(!select_asset_targets(nullptr, 3, 0x799fc73ff0, targets));

    LibraryMap rejected{};
    for (const char* line : {
        "799fc73000-799fc96000 r--p 00021000 fe:18 29840135 /system/lib64/libandroid.so\n",
        "799fc73000-799fc96000 rwxp 00021000 fe:18 29840135 /system/lib64/libandroid.so\n",
        "799fc73000-799fc96000 r-xp 00021000 fe:18 29840135 /system/lib64/libandroid.so.bak\n",
        "799fc73000-799fc96000 r-xp 00021000 fe:18 29840135 /system/lib64/libandroid.so (deleted)\n",
        "799fc73000-799fc96000 r-xp 00021000 fe:18 29840135 /data/local/tmp/libandroid.so\n",
        "799fc96000-799fc73000 r-xp 00021000 fe:18 29840135 /system/lib64/libandroid.so\n",
        "799fc73000-799fc96000 r-xp 00021000 fe:18 0 /system/lib64/libandroid.so\n",
        "malformed", ""
    }) assert(!parse_library_map(line, rejected));
    assert(!parse_library_map(nullptr, rejected));

    maps[3] = maps[0];
    maps[3].start += 0x10000000000;
    maps[3].end += 0x10000000000;
    maps[3].inode++; // Different file at the same pathname is never hooked.
    assert(select_asset_targets(maps, 4, 0x7ab155dff0, targets) && targets.count == 2);
    maps[3].inode = maps[0].inode;
    maps[3].minor++; // Different device is never hooked.
    assert(select_asset_targets(maps, 4, 0x7ab155dff0, targets) && targets.count == 2);
    maps[3] = maps[0]; // Duplicate/ambiguous mapping fails before patching.
    assert(!select_asset_targets(maps, 4, 0x7ab155dff0, targets));
    for (unsigned i = 0; i < 6; ++i) {
        maps[i] = {0x100000 + i * 0x10000, 0x102000 + i * 0x10000, 0x21000, 1234, 254, 24};
    }
    assert(select_asset_targets(maps, 4, 0x100ff0, targets) && targets.count == 4);
    assert(!select_asset_targets(maps, 5, 0x100ff0, targets));
}
