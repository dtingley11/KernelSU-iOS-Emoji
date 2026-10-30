#pragma once
#include <jni.h>
#include <cassert>
#include <sys/socket.h>
#include <unistd.h>
#include "core.h"
namespace zygisk {
enum Option { DLCLOSE_MODULE_LIBRARY = 1 };
struct AppSpecializeArgs { jint uid; jstring nice_name; };
struct ServerSpecializeArgs {};
struct Api {
    unsigned unloads = 0, connections = 0;
    bool armed = false, bad_hook_header = false;
    void setOption(Option option) { assert(option == DLCLOSE_MODULE_LIBRARY); ++unloads; }
    int connectCompanion() {
        ++connections;
        int sockets[2];
        assert(socketpair(AF_UNIX, SOCK_STREAM, 0, sockets) == 0);
        clash_font::Header headers[] = {{clash_font::magic, armed ? 4ULL : 0ULL},
            {clash_font::magic, armed && !bad_hook_header ? 4ULL : 0ULL}};
        assert(write(sockets[0], headers, sizeof(headers)) == sizeof(headers));
        if (armed) assert(write(sockets[0], "fonthook", 8) == 8);
        close(sockets[0]);
        return sockets[1];
    }
};
class ModuleBase {
public:
    virtual void onLoad(Api*, JNIEnv*) {}
    virtual void preAppSpecialize(AppSpecializeArgs*) {}
    virtual void postAppSpecialize(const AppSpecializeArgs*) {}
    virtual void preServerSpecialize(ServerSpecializeArgs*) {}
};
}
#define REGISTER_ZYGISK_MODULE(type)
#define REGISTER_ZYGISK_COMPANION(callback) static auto unused_companion __attribute__((unused)) = callback;
