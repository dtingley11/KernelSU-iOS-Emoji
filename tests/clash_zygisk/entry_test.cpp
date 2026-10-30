#include <cassert>
#include <cstring>
#include <dlfcn.h>
#include <fcntl.h>
#include <string>
#include <unistd.h>
#include <android/dlext.h>
#include "hook_api.h"

static unsigned loads = 0, starts = 0;
static bool loader_failure = false;
static uid_t current_uid = 10474;
static uid_t fixture_getuid() { return current_uid; }
static bool start_helper(JNIEnv*, int fd, uint32_t abi, uint32_t expected_uid) {
    ++starts;
    assert(abi == clash_font::hook_abi);
    assert(expected_uid == 10474);
    char bytes[4];
    assert(read(fd, bytes, sizeof(bytes)) == 4 && std::memcmp(bytes, "font", 4) == 0);
    assert((fcntl(fd, F_GET_SEALS) & F_SEAL_WRITE) != 0);
    close(fd);
    return true;
}
static void* fixture_dlsym(void* handle, const char* name) {
    assert(handle == reinterpret_cast<void*>(0x1234));
    assert(std::strcmp(name, clash_font::hook_entry) == 0);
    return reinterpret_cast<void*>(start_helper);
}
extern "C" void* android_dlopen_ext(const char* name, int flags, const android_dlextinfo* info) {
    ++loads;
    assert(std::strcmp(name, "clash-font-hook.so") == 0 && flags == RTLD_NOW);
    assert(info->flags == ANDROID_DLEXT_USE_LIBRARY_FD);
    char bytes[4];
    assert(read(info->library_fd, bytes, sizeof(bytes)) == 4 && std::memcmp(bytes, "hook", 4) == 0);
    assert((fcntl(info->library_fd, F_GET_SEALS) & F_SEAL_WRITE) != 0);
    return loader_failure ? nullptr : reinterpret_cast<void*>(0x1234);
}
extern "C" int __android_log_print(int, const char*, const char*, ...) { return 0; }

#define CLASH_FONT_UID 10474
#define CLASH_APK_BYTES 4ULL
#define CLASH_HOOK_BYTES 4ULL
#define getuid fixture_getuid
#define dlsym fixture_dlsym
#ifdef INTEGRATED_ENTRY
#include "integrated.cpp"
#else
#include "module.cpp"
#endif
#undef getuid
#undef dlsym

int main() {
    std::u16string clash = u"com.supercell.clashofclans";
    std::u16string duck = u"com.eltavine.duckdetector";
    std::u16string child = u"com.supercell.clashofclans:worker";
    for (const auto& args : {zygisk::AppSpecializeArgs{20474, &clash},
                            zygisk::AppSpecializeArgs{10474, &duck},
                            zygisk::AppSpecializeArgs{10474, &child},
                            zygisk::AppSpecializeArgs{10474, nullptr}}) {
        auto mutable_args = args;
        zygisk::Api api;
        JNIEnv env;
        ClashFontModule module;
        module.onLoad(&api, &env);
        module.preAppSpecialize(&mutable_args);
        module.postAppSpecialize(&mutable_args);
        assert(api.unloads == 1 && api.connections == 0 && loads == 0 && starts == 0);
    }
#ifdef INTEGRATED_ENTRY
    constexpr unsigned scenarios = 6;
#else
    constexpr unsigned scenarios = 5;
#endif
    for (unsigned scenario = 0; scenario < scenarios; ++scenario) {
        zygisk::Api api;
        api.armed = scenario != 0;
        api.bad_hook_header = scenario == 2;
        if (scenario == 5) api.configured_uid = 10475;
        current_uid = scenario == 3 ? 10475 : 10474;
        loader_failure = scenario == 4;
        JNIEnv env;
        ClashFontModule module;
        module.onLoad(&api, &env);
        zygisk::AppSpecializeArgs args{10474, &clash};
        unsigned previous_loads = loads, previous_starts = starts;
        module.preAppSpecialize(&args);
        assert(loads == previous_loads); // No helper loading before specialization.
        module.postAppSpecialize(&args);
        assert(api.unloads == 1 && api.connections == 1);
        assert(loads == previous_loads + (scenario == 1 || scenario == 4));
        assert(starts == previous_starts + (scenario == 1));
    }
#ifdef INTEGRATED_ENTRY
    // Persistent mode can supply the same enabled UID on successive launches.
    current_uid = 10474;
    loader_failure = false;
    for (unsigned launch = 0; launch < 2; ++launch) {
        zygisk::Api api;
        api.armed = true;
        JNIEnv env;
        ClashFontModule module;
        module.onLoad(&api, &env);
        zygisk::AppSpecializeArgs args{10474, &clash};
        unsigned before = starts;
        module.preAppSpecialize(&args);
        module.postAppSpecialize(&args);
        assert(starts == before + 1 && api.unloads == 1);
    }
#endif
    zygisk::Api api;
    JNIEnv env;
    ClashFontModule module;
    module.onLoad(&api, &env);
    zygisk::ServerSpecializeArgs server;
    module.preServerSpecialize(&server);
    assert(api.unloads == 1 && api.connections == 0);
}
