// Minimal entry: no Dobby, Android asset API, or C++ runtime dependency.
#include <android/dlext.h>
#include <android/log.h>
#include <cstdlib>
#include <dlfcn.h>
#include "zygisk-api-4.hpp"
#include "persistent.h"
#include "hook_api.h"
#include "memory_file.h"

#if !defined(CLASH_APK_BYTES) || !defined(CLASH_HOOK_BYTES)
#error Build with the verified Clash UID and audited payload lengths
#endif

namespace {
constexpr const char* tag = "ClashFontZygisk";
constexpr const char* module_root = "/data/adb/modules/iOS_Emoji_KSU/clash";
constexpr std::size_t total_bytes = CLASH_APK_BYTES + CLASH_HOOK_BYTES;
static_assert(CLASH_APK_BYTES > 0 && CLASH_HOOK_BYTES > 0 && total_bytes <= clash_font::max_payload);

bool send_file(int socket, int file, std::size_t remaining, int64_t deadline) {
    unsigned char buffer[65536];
    while (remaining) {
        std::size_t wanted = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
        ssize_t count = read(file, buffer, wanted);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0 || !clash_font::socket_io(socket, buffer, count, true, deadline)) return false;
        remaining -= static_cast<std::size_t>(count);
    }
    return true;
}

// Fixed files only. No paths, commands, or operations are accepted from clients.
void serve_payload(int socket) {
    struct ucred peer{};
    socklen_t peer_size = sizeof(peer);
    if (getsockopt(socket, SOL_SOCKET, SO_PEERCRED, &peer, &peer_size) != 0 || peer.uid != 0) return;
    int64_t deadline = clash_font::now_ms() + 5000;
    int directory = open(module_root, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    int uid = directory < 0 ? -1 : clash_font::enabled_uid(directory);
    int font = uid < 0 ? -1 : clash_font::open_owned_payload(directory, "font-assets.apk", CLASH_APK_BYTES);
    int hook = font < 0 ? -1 : clash_font::open_owned_payload(directory, "font-hook.so", CLASH_HOOK_BYTES);
    if (directory >= 0) close(directory);
    bool ready = font >= 0 && hook >= 0;
    clash_font::Header headers[] = {
        {clash_font::magic, ready ? static_cast<uint64_t>(uid) : 0},
        {clash_font::magic, ready ? CLASH_APK_BYTES : 0},
        {clash_font::magic, ready ? CLASH_HOOK_BYTES : 0}
    };
    if (clash_font::socket_io(socket, headers, sizeof(headers), true, deadline) && ready) {
        if (send_file(socket, font, CLASH_APK_BYTES, deadline))
            send_file(socket, hook, CLASH_HOOK_BYTES, deadline);
    }
    if (font >= 0) close(font);
    if (hook >= 0) close(hook);
}

class ClashFontModule final : public zygisk::ModuleBase {
public:
    void onLoad(zygisk::Api* api, JNIEnv* env) override { api_ = api; env_ = env; }

    void preAppSpecialize(zygisk::AppSpecializeArgs* args) override {
        // Every process, including Clash, unloads this entry after the callback.
        // All resident hooks and state belong exclusively to the separate helper.
        api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
        if (!args || args->uid < 10000 || args->uid >= 20000 || !args->nice_name || env_->ExceptionCheck()) return;
        jsize size = env_->GetStringLength(args->nice_name);
        if (size != static_cast<jsize>(sizeof(clash_font::process_name) - 1)) return;
        jchar name[sizeof(clash_font::process_name) - 1];
        env_->GetStringRegion(args->nice_name, 0, size, name);
        if (env_->ExceptionCheck()) { env_->ExceptionClear(); return; }
        if (!clash_font::matches_scope(args->uid, args->uid, name, size)) return;
        __android_log_print(ANDROID_LOG_INFO, tag, "TARGET_SELECTED pid=%d uid=%d", getpid(), args->uid);
        int socket = api_->connectCompanion();
        if (socket >= 0) {
            clash_font::Header headers[3]{};
            int64_t deadline = clash_font::now_ms() + 5000;
            if (clash_font::socket_io(socket, headers, sizeof(headers), false, deadline) &&
                headers[0].marker == clash_font::magic && headers[0].size == static_cast<uint64_t>(args->uid) &&
                clash_font::valid_header(headers[1], CLASH_APK_BYTES) &&
                clash_font::valid_header(headers[2], CLASH_HOOK_BYTES)) {
                payload_ = static_cast<unsigned char*>(std::malloc(total_bytes));
                target_uid_ = args->uid;
                if (payload_ && !clash_font::socket_io(socket, payload_, total_bytes, false, deadline)) {
                    std::free(payload_);
                    payload_ = nullptr;
                }
            }
            close(socket);
        }
        if (!payload_)
            __android_log_print(ANDROID_LOG_WARN, tag, "DISABLED_OR_PREPARE_FAILED original assets retained");
    }

    void postAppSpecialize(const zygisk::AppSpecializeArgs* args) override {
        if (!payload_) return;
        if (!args || args->uid != target_uid_ || getuid() != static_cast<uid_t>(target_uid_)) {
            std::free(payload_);
            payload_ = nullptr;
            return;
        }
        // Memory files and the ordinary Android loader run only in selected Clash.
        int font = clash_font::sealed_memory_file("clash-emoji-font-assets", payload_, CLASH_APK_BYTES);
        int hook = font < 0 ? -1 : clash_font::sealed_memory_file("clash-emoji-font-hook",
            payload_ + CLASH_APK_BYTES, CLASH_HOOK_BYTES);
        std::free(payload_);
        payload_ = nullptr;
        if (font < 0 || hook < 0) {
            if (font >= 0) close(font);
            if (hook >= 0) close(hook);
            __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=memfd errno=%d", errno);
            return;
        }
        android_dlextinfo info{};
        info.flags = ANDROID_DLEXT_USE_LIBRARY_FD;
        info.library_fd = hook;
        void* handle = android_dlopen_ext("clash-font-hook.so", RTLD_NOW | RTLD_LOCAL, &info);
        close(hook);
        if (!handle) {
            close(font);
            __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=helper-load error=%s", dlerror());
            return;
        }
        // Deliberately keep a successfully loaded helper resident, including failures.
        // No helper function or data refers back to this entry library.
        auto start = reinterpret_cast<clash_font::StartHook>(dlsym(handle, clash_font::hook_entry));
        if (!start) {
            close(font);
            __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=helper-entry");
            return;
        }
        __android_log_print(ANDROID_LOG_INFO, tag, "HELPER_LOADED entry-unloads-after-callback");
        start(env_, font, clash_font::hook_abi, static_cast<uint32_t>(target_uid_)); // Helper takes ownership of font.
    }

    void preServerSpecialize([[maybe_unused]] zygisk::ServerSpecializeArgs* args) override {
        api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
    }

private:
    zygisk::Api* api_ = nullptr;
    JNIEnv* env_ = nullptr;
    unsigned char* payload_ = nullptr;
    jint target_uid_ = -1;
};
}
REGISTER_ZYGISK_MODULE(ClashFontModule)
REGISTER_ZYGISK_COMPANION(serve_payload)
