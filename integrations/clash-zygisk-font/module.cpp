#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <sys/mman.h>
#include "zygisk-api-4.hpp"
#include "dobby.h"
#include "core.h"
#include "font_redirect.h"
#include "library_maps.h"

#if !defined(CLASH_FONT_UID) || !defined(CLASH_FONT_BYTES) || !defined(CLASH_APK_BYTES)
#error Build with the verified Clash UID and audited payload lengths
#endif

namespace {
constexpr const char* tag = "ClashFontZygisk";
constexpr const char* module_root = "/data/adb/modules/ios_emoji_clash_zygisk_font";
clash_font::FontRedirect redirects[clash_font::max_providers];
jobject assets_owner = nullptr;
std::atomic<unsigned> served{0}, fallback{0};

template<std::size_t Provider>
AAsset* open_asset(AAssetManager* manager, const char* path, int mode) {
    clash_font::Outcome outcome;
    AAsset* result = redirects[Provider].open(manager, path, mode, outcome);
    if (outcome == clash_font::Outcome::Served && served.fetch_add(1) < 8) {
        __android_log_print(ANDROID_LOG_INFO, tag, "FONT_SERVED bytes=%lld mode=%d provider=%zu",
            static_cast<long long>(redirects[Provider].expected_size), mode, Provider);
    } else if (outcome == clash_font::Outcome::Fallback && fallback.fetch_add(1) < 8) {
        __android_log_print(ANDROID_LOG_WARN, tag, "FONT_FALLBACK original asset retained");
    }
    return result;
}

bool find_asset_targets(clash_font::AssetTargets& targets) {
    FILE* file = std::fopen("/proc/self/maps", "re");
    if (!file) return false;
    clash_font::LibraryMap maps[32]{};
    std::size_t count = 0;
    char line[1024];
    bool valid = true;
    while (std::fgets(line, sizeof(line), file)) {
        clash_font::LibraryMap map{};
        if (!clash_font::parse_library_map(line, map)) continue;
        if (count == sizeof(maps) / sizeof(maps[0])) { valid = false; break; }
        maps[count++] = map;
    }
    valid = valid && !std::ferror(file);
    std::fclose(file);
    return valid && clash_font::select_asset_targets(maps, count,
        reinterpret_cast<uintptr_t>(AAssetManager_open), targets);
}

// No client-supplied paths, commands, mount operations, or profile changes.
void serve_payload(int socket) {
    struct ucred peer{};
    socklen_t peer_size = sizeof(peer);
    if (getsockopt(socket, SOL_SOCKET, SO_PEERCRED, &peer, &peer_size) != 0 || peer.uid != 0) return;
    int64_t deadline = clash_font::now_ms() + 5000;
    int directory = open(module_root, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    int payload = directory < 0 ? -1 : clash_font::take_payload(directory, CLASH_APK_BYTES);
    if (directory >= 0) close(directory);
    clash_font::Header header{clash_font::magic, payload < 0 ? 0 : CLASH_APK_BYTES};
    if (!clash_font::socket_io(socket, &header, sizeof(header), true, deadline)) {
        if (payload >= 0) close(payload);
        return;
    }
    if (payload < 0) return;
    unsigned char buffer[65536];
    std::size_t remaining = CLASH_APK_BYTES;
    while (remaining) {
        std::size_t wanted = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
        ssize_t count = read(payload, buffer, wanted);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0 || !clash_font::socket_io(socket, buffer, count, true, deadline)) break;
        remaining -= static_cast<std::size_t>(count);
    }
    close(payload);
}

bool jni_ok(JNIEnv* env, const char* stage) {
    if (!env->ExceptionCheck()) return true;
    env->ExceptionClear();
    __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=%s java exception", stage);
    return false;
}

// Build a separate AssetManager from a sealed asset-only APK. Never attach it to
// the game's Resources. These framework methods are private and version-sensitive;
// unavailable methods cause an ordinary failure, without changing hidden-API policy.
bool prepare_assets(JNIEnv* env, int fd) {
    if (env->PushLocalFrame(24) != JNI_OK) {
        jni_ok(env, "local-frame");
        close(fd);
        return false;
    }
    bool success = false;
    bool adopted = false;
    jobject parcel = nullptr;
    auto find = [env](const char* name) {
        jclass result = env->FindClass(name);
        return jni_ok(env, name) ? result : nullptr;
    };
    auto method = [env](jclass cls, const char* name, const char* signature, bool is_static) {
        jmethodID result = is_static ? env->GetStaticMethodID(cls, name, signature)
                                    : env->GetMethodID(cls, name, signature);
        return jni_ok(env, name) ? result : nullptr;
    };
    jclass parcel_class = find("android/os/ParcelFileDescriptor");
    jclass apk_class = find("android/content/res/ApkAssets");
    jclass builder_class = find("android/content/res/AssetManager$Builder");
    jmethodID parcel_close = nullptr;
    if (jni_ok(env, "classes") && parcel_class && apk_class && builder_class) {
        jmethodID adopt = method(parcel_class, "adoptFd", "(I)Landroid/os/ParcelFileDescriptor;", true);
        jmethodID get_fd = method(parcel_class, "getFileDescriptor", "()Ljava/io/FileDescriptor;", false);
        parcel_close = method(parcel_class, "close", "()V", false);
        jmethodID load = method(apk_class, "loadFromFd",
            "(Ljava/io/FileDescriptor;Ljava/lang/String;ILandroid/content/res/loader/AssetsProvider;)Landroid/content/res/ApkAssets;", true);
        jmethodID constructor = method(builder_class, "<init>", "()V", false);
        jmethodID add = method(builder_class, "addApkAssets",
            "(Landroid/content/res/ApkAssets;)Landroid/content/res/AssetManager$Builder;", false);
        jmethodID build = method(builder_class, "build", "()Landroid/content/res/AssetManager;", false);
        if (adopt && get_fd && parcel_close && load && constructor && add && build) {
            parcel = env->CallStaticObjectMethod(parcel_class, adopt, fd);
            adopted = parcel != nullptr;
            if (jni_ok(env, "adopt") && parcel) {
                jobject descriptor = env->CallObjectMethod(parcel, get_fd);
                bool descriptor_ok = jni_ok(env, "descriptor");
                jstring name = descriptor_ok ? env->NewStringUTF("Clash emoji font assets") : nullptr;
                if (jni_ok(env, "name") && descriptor && name) {
                    jobject apk = env->CallStaticObjectMethod(apk_class, load, descriptor, name, 0, nullptr);
                    if (jni_ok(env, "apk") && apk) {
                        jobject builder = env->NewObject(builder_class, constructor);
                        if (jni_ok(env, "builder") && builder) {
                            env->CallObjectMethod(builder, add, apk);
                            if (jni_ok(env, "add")) {
                                jobject manager = env->CallObjectMethod(builder, build);
                                if (jni_ok(env, "build") && manager) {
                                    AAssetManager* native = AAssetManager_fromJava(env, manager);
                                    if (jni_ok(env, "native") && native) {
                                        AAsset* sample = AAssetManager_open(native, clash_font::replacement_path, AASSET_MODE_RANDOM);
                                        if (sample) {
                                            bool correct = AAsset_getLength64(sample) == CLASH_FONT_BYTES;
                                            AAsset_close(sample);
                                            if (correct) {
                                                assets_owner = env->NewGlobalRef(manager);
                                                if (jni_ok(env, "retain") && assets_owner) {
                                                    for (auto& redirect : redirects) {
                                                        redirect.replacements = native;
                                                        redirect.expected_size = CLASH_FONT_BYTES;
                                                    }
                                                    success = true;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    if (adopted) {
        env->CallVoidMethod(parcel, parcel_close);
        jni_ok(env, "close");
    } else {
        close(fd);
    }
    env->PopLocalFrame(nullptr);
    return success;
}

class ClashFontModule final : public zygisk::ModuleBase {
public:
    void onLoad(zygisk::Api* api, JNIEnv* env) override { api_ = api; env_ = env; }

    void preAppSpecialize(zygisk::AppSpecializeArgs* args) override {
        if (!args || args->uid != CLASH_FONT_UID || !args->nice_name || env_->ExceptionCheck()) {
            api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
            return;
        }
        jsize size = env_->GetStringLength(args->nice_name);
        if (size != static_cast<jsize>(sizeof(clash_font::process_name) - 1)) {
            api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
            return;
        }
        jchar name[sizeof(clash_font::process_name) - 1];
        env_->GetStringRegion(args->nice_name, 0, size, name);
        if (!jni_ok(env_, "scope") || !clash_font::matches_scope(args->uid, CLASH_FONT_UID, name, size)) {
            api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
            return;
        }
        __android_log_print(ANDROID_LOG_INFO, tag, "TARGET_SELECTED pid=%d uid=%d", getpid(), args->uid);
        int socket = api_->connectCompanion();
        if (socket >= 0) {
            clash_font::Header header{};
            int64_t deadline = clash_font::now_ms() + 5000;
            if (clash_font::socket_io(socket, &header, sizeof(header), false, deadline) &&
                clash_font::valid_header(header, CLASH_APK_BYTES)) {
                payload_ = static_cast<unsigned char*>(std::malloc(CLASH_APK_BYTES));
                if (payload_ && !clash_font::socket_io(socket, payload_, CLASH_APK_BYTES, false, deadline)) {
                    std::free(payload_);
                    payload_ = nullptr;
                }
            }
            close(socket);
        }
        if (!payload_) {
            __android_log_print(ANDROID_LOG_WARN, tag, "NOT_ARMED_OR_PREPARE_FAILED original assets retained");
            api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
        }
    }

    void postAppSpecialize([[maybe_unused]] const zygisk::AppSpecializeArgs* args) override {
        if (!payload_) return;
        int fd = memfd_create("clash-emoji-font-assets", MFD_CLOEXEC | MFD_ALLOW_SEALING);
        bool complete = fd >= 0;
        std::size_t offset = 0;
        while (complete && offset < CLASH_APK_BYTES) {
            ssize_t count = write(fd, payload_ + offset, CLASH_APK_BYTES - offset);
            if (count < 0 && errno == EINTR) continue;
            if (count <= 0) complete = false;
            else offset += static_cast<std::size_t>(count);
        }
        std::free(payload_);
        payload_ = nullptr;
        if (complete) complete = lseek(fd, 0, SEEK_SET) == 0 &&
            fcntl(fd, F_ADD_SEALS, F_SEAL_SEAL | F_SEAL_WRITE | F_SEAL_SHRINK | F_SEAL_GROW) == 0;
        if (!complete) {
            if (fd >= 0) close(fd);
            __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=memfd errno=%d", errno);
            api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
            return;
        }
        if (!prepare_assets(env_, fd)) {
            __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=asset-manager");
            api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
            return;
        }
        clash_font::AssetTargets targets;
        if (!find_asset_targets(targets)) {
            __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=provider-maps");
            if (assets_owner) env_->DeleteGlobalRef(assets_owner);
            assets_owner = nullptr;
            api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
            return;
        }
        __android_log_print(ANDROID_LOG_INFO, tag, "PROVIDERS_FOUND count=%zu", targets.count);
        constexpr clash_font::AssetOpen callbacks[] = {
            open_asset<0>, open_asset<1>, open_asset<2>, open_asset<3>
        };
        static_assert(sizeof(callbacks) / sizeof(callbacks[0]) == clash_font::max_providers);
        // Keep this library resident once a hook installation is attempted,
        // including partial hook failures. Never unload a possible callback.
        for (std::size_t i = 0; i < targets.count; ++i) {
            int result = DobbyHook(reinterpret_cast<void*>(targets.addresses[i]),
                reinterpret_cast<void*>(callbacks[i]), reinterpret_cast<void**>(&redirects[i].original));
            if (result != 0 || !redirects[i].original) {
                __android_log_print(ANDROID_LOG_ERROR, tag, "HOOK_FAILED provider=%zu status=%d", i, result);
                return;
            }
            __android_log_print(ANDROID_LOG_INFO, tag, "PROVIDER_HOOKED index=%zu", i);
        }
        __android_log_print(ANDROID_LOG_INFO, tag, "HOOK_READY providers=%zu exact-font-only one-shot", targets.count);
    }

    void preServerSpecialize([[maybe_unused]] zygisk::ServerSpecializeArgs* args) override {
        api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
    }

private:
    zygisk::Api* api_ = nullptr;
    JNIEnv* env_ = nullptr;
    unsigned char* payload_ = nullptr;
};
}

REGISTER_ZYGISK_MODULE(ClashFontModule)
REGISTER_ZYGISK_COMPANION(serve_payload)
