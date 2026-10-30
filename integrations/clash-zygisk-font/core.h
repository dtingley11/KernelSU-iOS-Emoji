#pragma once
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

namespace clash_font {
inline constexpr char process_name[] = "com.supercell.clashofclans";
inline constexpr char target_path[] = "titan/fonts/NotoColorEmoji.ttf";
inline constexpr char replacement_path[] = "replacement.ttf";
inline constexpr uint64_t magic = 0x434c415348464e31;
inline constexpr uint64_t max_payload = 64ULL * 1024 * 1024;
struct Header { uint64_t marker; uint64_t size; };

inline bool matches_scope(int uid, int expected, const uint16_t* name, std::size_t length) {
    if (expected < 10000 || expected >= 20000 || uid != expected || !name ||
        length != sizeof(process_name) - 1) return false;
    for (std::size_t i = 0; i < length; ++i) {
        if (name[i] != static_cast<unsigned char>(process_name[i])) return false;
    }
    return true;
}

inline bool valid_header(const Header& header, uint64_t expected) {
    return header.marker == magic && expected > 0 && expected <= max_payload && header.size == expected;
}

inline int64_t now_ms() {
    struct timespec now{};
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) return -1;
    return now.tv_sec * 1000LL + now.tv_nsec / 1000000;
}

inline bool socket_io(int fd, void* buffer, std::size_t size, bool writing, int64_t deadline) {
    auto* bytes = static_cast<unsigned char*>(buffer);
    while (size) {
        int64_t current = now_ms();
        if (current < 0 || current >= deadline) return false;
        struct pollfd item{fd, static_cast<short>(writing ? POLLOUT : POLLIN), 0};
        int ready = poll(&item, 1, static_cast<int>(deadline - current));
        if (ready < 0 && errno == EINTR) continue;
        if (ready <= 0 || !(item.revents & item.events)) return false;
        ssize_t count = writing ? send(fd, bytes, size, MSG_DONTWAIT | MSG_NOSIGNAL)
                                : recv(fd, bytes, size, MSG_DONTWAIT);
        if (count < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (count <= 0) return false;
        bytes += count;
        size -= static_cast<std::size_t>(count);
    }
    return true;
}

inline bool owned_regular(const struct stat& info, uid_t owner) {
    return S_ISREG(info.st_mode) && info.st_uid == owner && !(info.st_mode & 0022);
}

// Callers supply compile-time module filenames, never socket request data.
inline int open_owned_payload(int directory, const char* name, uint64_t expected, uid_t owner = 0) {
    struct stat dir{}, payload{};
    if (expected == 0 || expected > max_payload || fstat(directory, &dir) != 0 ||
        !S_ISDIR(dir.st_mode) || dir.st_uid != owner || (dir.st_mode & 0022)) return -1;
    int fd = openat(directory, name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0) return -1;
    if (fstat(fd, &payload) != 0 || !owned_regular(payload, owner) || payload.st_size <= 0 ||
        static_cast<uint64_t>(payload.st_size) != expected) {
        close(fd);
        return -1;
    }
    return fd;
}

// The root handler uses owner=0. The parameter lets host tests use their own UID.
// This is an internal helper, not a socket request or arbitrary-path root API.
inline int take_payload(int directory, uint64_t expected, uid_t owner = 0) {
    struct stat dir{}, arm{};
    if (expected == 0 || expected > max_payload || fstat(directory, &dir) != 0 ||
        !S_ISDIR(dir.st_mode) || dir.st_uid != owner || (dir.st_mode & 0022)) return -1;
    int armed = openat(directory, "armed", O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (armed < 0) return -1;
    bool valid = fstat(armed, &arm) == 0 && owned_regular(arm, owner);
    close(armed);
    if (!valid || unlinkat(directory, "armed", 0) != 0) return -1;
    // Consumption precedes payload loading: a failed attempt is not retried.
    return open_owned_payload(directory, "font-assets.apk", expected, owner);
}
}
