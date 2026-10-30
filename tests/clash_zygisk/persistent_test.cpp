#include "persistent.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
using namespace clash_font;

int main() {
    char path[] = "/tmp/clash-persistent-XXXXXX";
    assert(mkdtemp(path));
    int dir = open(path, O_RDONLY | O_DIRECTORY);
    assert(dir >= 0);
    uid_t owner = geteuid();
    assert(enabled_uid(dir, owner) == -1);
    for (const char* value : {"10474\n", "19999", "10000\n", "10474"}) {
        int fd = openat(dir, "enabled", O_CREAT | O_TRUNC | O_WRONLY, 0600);
        assert(fd >= 0 && write(fd, value, std::strlen(value)) == static_cast<ssize_t>(std::strlen(value)));
        close(fd);
        int expected = std::atoi(value);
        assert(enabled_uid(dir, owner) == expected);
        assert(enabled_uid(dir, owner) == expected); // Read never consumes setting.
    }
    for (const char* value : {"", "0", "09999", "20000", "104740", "10474;", "10474\n0", "1047x", " 10474"}) {
        int fd = openat(dir, "enabled", O_WRONLY | O_TRUNC);
        assert(fd >= 0 && write(fd, value, std::strlen(value)) == static_cast<ssize_t>(std::strlen(value)));
        close(fd);
        assert(enabled_uid(dir, owner) == -1);
    }
    int fd = openat(dir, "enabled", O_WRONLY | O_TRUNC);
    assert(fd >= 0 && write(fd, "10474\n", 6) == 6);
    close(fd);
    assert(enabled_uid(dir, owner + 1) == -1);
    assert(fchmodat(dir, "enabled", 0666, 0) == 0);
    assert(enabled_uid(dir, owner) == -1);
    assert(unlinkat(dir, "enabled", 0) == 0);
    assert(symlinkat("missing", dir, "enabled") == 0);
    assert(enabled_uid(dir, owner) == -1);
    assert(unlinkat(dir, "enabled", 0) == 0);
    close(dir);
    assert(rmdir(path) == 0);
}
