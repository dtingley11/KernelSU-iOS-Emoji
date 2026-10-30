#include "core.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <vector>

using namespace clash_font;

static void touch(int dir, const char* name, const char* data = "") {
    int fd = openat(dir, name, O_CREAT | O_TRUNC | O_WRONLY, 0600);
    assert(fd >= 0);
    assert(write(fd, data, std::strlen(data)) == static_cast<ssize_t>(std::strlen(data)));
    close(fd);
}

int main() {
    std::vector<uint16_t> name(process_name, process_name + sizeof(process_name) - 1);
    assert(matches_scope(10474, 10474, name.data(), name.size()));
    assert(!matches_scope(10475, 10474, name.data(), name.size()));
    assert(!matches_scope(0, 0, name.data(), name.size()));
    assert(!matches_scope(20000, 20000, name.data(), name.size()));
    assert(!matches_scope(10474, 10474, nullptr, name.size()));
    assert(!matches_scope(10474, 10474, name.data(), name.size() - 1));
    name.push_back(':');
    assert(!matches_scope(10474, 10474, name.data(), name.size()));
    name.pop_back();
    name[0] = 'x';
    assert(!matches_scope(10474, 10474, name.data(), name.size()));
    assert(valid_header({magic, 1024}, 1024));
    assert(!valid_header({magic + 1, 1024}, 1024));
    assert(!valid_header({magic, 1023}, 1024));
    assert(!valid_header({magic, 0}, 0));
    assert(!valid_header({magic, max_payload + 1}, max_payload + 1));

    int sockets[2];
    assert(socketpair(AF_UNIX, SOCK_STREAM, 0, sockets) == 0);
    std::vector<unsigned char> sent(1024 * 1024, 0x59), received(sent.size());
    std::thread sender([&] {
        assert(socket_io(sockets[0], sent.data(), sent.size(), true, now_ms() + 3000));
    });
    assert(socket_io(sockets[1], received.data(), received.size(), false, now_ms() + 3000));
    sender.join();
    assert(sent == received);
    unsigned char byte{};
    assert(!socket_io(sockets[1], &byte, 1, false, now_ms() + 20));
    assert(!socket_io(sockets[1], &byte, 1, false, now_ms() - 1));
    close(sockets[0]);
    assert(!socket_io(sockets[1], &byte, 1, false, now_ms() + 100));
    close(sockets[1]);

    char path[] = "/tmp/clash-one-shot-XXXXXX";
    assert(mkdtemp(path));
    int dir = open(path, O_RDONLY | O_DIRECTORY);
    assert(dir >= 0);
    uid_t owner = geteuid();
    touch(dir, "font-assets.apk", "font");
    assert(take_payload(dir, 4, owner) == -1); // Unarmed never serves.
    touch(dir, "armed");
    int fd = take_payload(dir, 4, owner);
    assert(fd >= 0);
    char bytes[4];
    assert(read(fd, bytes, 4) == 4 && std::memcmp(bytes, "font", 4) == 0);
    close(fd);
    assert(take_payload(dir, 4, owner) == -1); // Exactly one attempt.
    touch(dir, "armed");
    assert(take_payload(dir, 3, owner) == -1); // Failure consumes marker too.
    assert(faccessat(dir, "armed", F_OK, 0) == -1);
    touch(dir, "armed");
    assert(fchmodat(dir, "font-assets.apk", 0666, 0) == 0);
    assert(take_payload(dir, 4, owner) == -1);
    assert(fchmodat(dir, "font-assets.apk", 0600, 0) == 0);
    assert(symlinkat("font-assets.apk", dir, "armed") == 0);
    assert(take_payload(dir, 4, owner) == -1); // Marker symlinks rejected.
    assert(unlinkat(dir, "armed", 0) == 0);
    assert(unlinkat(dir, "font-assets.apk", 0) == 0);
    touch(dir, "real", "font");
    assert(symlinkat("real", dir, "font-assets.apk") == 0);
    touch(dir, "armed");
    assert(take_payload(dir, 4, owner) == -1); // Payload symlinks rejected.
    assert(unlinkat(dir, "font-assets.apk", 0) == 0);
    touch(dir, "font-assets.apk", "font");
    touch(dir, "armed");
    assert(take_payload(dir, 4, owner + 1) == -1);
    assert(fchmod(dir, 0777) == 0);
    assert(take_payload(dir, 4, owner) == -1);
    assert(fchmod(dir, 0700) == 0);
    assert(unlinkat(dir, "armed", 0) == 0);
    assert(unlinkat(dir, "font-assets.apk", 0) == 0);
    assert(unlinkat(dir, "real", 0) == 0);
    close(dir);
    assert(rmdir(path) == 0);
}
