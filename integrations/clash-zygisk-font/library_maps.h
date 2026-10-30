#pragma once
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace clash_font {
inline constexpr std::size_t max_providers = 4;
struct LibraryMap {
    uintptr_t start, end;
    uint64_t offset, inode;
    unsigned major, minor;
};
struct AssetTargets {
    uintptr_t addresses[max_providers]{};
    std::size_t count = 0;
};

// Consider only readable executable mappings of the exact system asset library.
inline bool parse_library_map(const char* line, LibraryMap& result) {
    unsigned long long start, end, offset, inode;
    unsigned major, minor;
    char permissions[5]{};
    int path_offset = 0;
    if (!line || std::sscanf(line, "%llx-%llx %4s %llx %x:%x %llu %n",
        &start, &end, permissions, &offset, &major, &minor, &inode, &path_offset) != 7 ||
        !path_offset || std::strlen(permissions) != 4 || permissions[0] != 'r' ||
        permissions[1] != '-' || permissions[2] != 'x' || permissions[3] != 'p' ||
        start >= end || end > UINTPTR_MAX || inode == 0) return false;
    const char* path = line + path_offset;
    constexpr char expected[] = "/system/lib64/libandroid.so";
    if (std::strncmp(path, expected, sizeof(expected) - 1) != 0) return false;
    path += sizeof(expected) - 1;
    if (*path != '\0' && !(*path == '\n' && path[1] == '\0')) return false;
    result = {static_cast<uintptr_t>(start), static_cast<uintptr_t>(end),
              offset, inode, major, minor};
    return true;
}

// Match the linked provider's device/inode and symbol file offset. Virtual
// addresses differ between linker namespaces; file identity and offsets do not.
inline bool select_asset_targets(const LibraryMap* maps, std::size_t count,
                                 uintptr_t linked, AssetTargets& result) {
    result = {};
    if (!maps) return false;
    const LibraryMap* own = nullptr;
    for (std::size_t i = 0; i < count; ++i) {
        if (maps[i].start <= linked && linked < maps[i].end) {
            if (own) return false;
            own = &maps[i];
        }
    }
    if (!own || linked - own->start > UINT64_MAX - own->offset) return false;
    uint64_t symbol_offset = own->offset + linked - own->start;
    for (std::size_t i = 0; i < count; ++i) {
        const LibraryMap& map = maps[i];
        if (map.inode != own->inode || map.major != own->major || map.minor != own->minor ||
            map.start >= map.end || symbol_offset < map.offset ||
            symbol_offset - map.offset >= map.end - map.start) continue;
        uintptr_t address = map.start + static_cast<uintptr_t>(symbol_offset - map.offset);
        for (std::size_t j = 0; j < result.count; ++j) {
            if (result.addresses[j] == address) return false;
        }
        if (result.count == max_providers) return false;
        result.addresses[result.count++] = address;
    }
    return result.count != 0;
}
}
