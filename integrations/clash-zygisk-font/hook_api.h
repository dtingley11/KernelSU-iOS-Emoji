#pragma once
#include <jni.h>
#include <cstdint>

namespace clash_font {
inline constexpr uint32_t hook_abi = 2;
inline constexpr char hook_entry[] = "clash_font_start";
// The helper always takes ownership of font_fd. No callbacks point to the entry.
using StartHook = bool (*)(JNIEnv* env, int font_fd, uint32_t abi, uint32_t expected_uid);
}
