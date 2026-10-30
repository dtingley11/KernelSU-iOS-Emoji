#pragma once
#include <cerrno>
#include <cstddef>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

namespace clash_font {
inline int sealed_memory_file(const char* name, const unsigned char* bytes, std::size_t size) {
    if (!bytes || !size) return -1;
    int fd = memfd_create(name, MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (fd < 0) return -1;
    std::size_t offset = 0;
    while (offset < size) {
        ssize_t count = write(fd, bytes + offset, size - offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) { close(fd); return -1; }
        offset += static_cast<std::size_t>(count);
    }
    if (lseek(fd, 0, SEEK_SET) != 0 ||
        fcntl(fd, F_ADD_SEALS, F_SEAL_SEAL | F_SEAL_WRITE | F_SEAL_SHRINK | F_SEAL_GROW) != 0) {
        close(fd);
        return -1;
    }
    return fd;
}
}
