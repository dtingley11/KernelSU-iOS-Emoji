#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <sys/mman.h>
#include "hook_api.h"
#include "dobby.h"
#include "core.h"
#include "font_redirect.h"
#include "library_maps.h"

#if !defined(CLASH_FONT_BYTES)
#error Build with the verified Clash UID and audited payload lengths
#endif

namespace {
constexpr const char* tag = "ClashFontZygisk";
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

} // namespace

extern "C" __attribute__((visibility("default")))
bool clash_font_start(JNIEnv* env, int font_fd, uint32_t abi, uint32_t expected_uid) {
    if (abi != clash_font::hook_abi || expected_uid < 10000 || expected_uid >= 20000 || getuid() != expected_uid) {
        close(font_fd);
        return false;
    }
    if (!prepare_assets(env, font_fd)) {
        __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=asset-manager");
        return false;
    }
    clash_font::AssetTargets targets;
    if (!find_asset_targets(targets)) {
        __android_log_print(ANDROID_LOG_WARN, tag, "PREPARE_FAILED stage=provider-maps");
        if (assets_owner) env->DeleteGlobalRef(assets_owner);
        assets_owner = nullptr;
        return false;
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
            return false;
        }
        __android_log_print(ANDROID_LOG_INFO, tag, "PROVIDER_HOOKED index=%zu", i);
    }
    __android_log_print(ANDROID_LOG_INFO, tag, "HOOK_READY providers=%zu exact-font-only", targets.count);
    return true;
}
