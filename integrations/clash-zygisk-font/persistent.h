#pragma once
#include "core.h"

namespace clash_font {
// The enabled file contains only a decimal user-0 UID, never shell commands.
inline int enabled_uid(int directory, uid_t owner = 0) {
    struct stat dir{}, file{};
    if (fstat(directory, &dir) != 0 || !S_ISDIR(dir.st_mode) || dir.st_uid != owner || (dir.st_mode & 0022)) return -1;
    int fd = openat(directory, "enabled", O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0) return -1;
    bool valid = fstat(fd, &file) == 0 && owned_regular(file, owner) && file.st_size >= 5 && file.st_size <= 6;
    char bytes[8]{};
    ssize_t count = valid ? read(fd, bytes, sizeof(bytes)) : -1;
    close(fd);
    if (count != file.st_size || count < 5 || count > 6) return -1;
    if (count == 6 && bytes[5] != '\n') return -1;
    unsigned value = 0;
    for (unsigned i = 0; i < 5; ++i) {
        if (bytes[i] < '0' || bytes[i] > '9') return -1;
        value = value * 10 + static_cast<unsigned>(bytes[i] - '0');
    }
    return value >= 10000 && value < 20000 ? static_cast<int>(value) : -1;
}
}
