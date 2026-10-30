#pragma once
#include <android/asset_manager.h>
#include <cstdint>

namespace clash_font {
using AssetOpen = AAsset* (*)(AAssetManager*, const char*, int);
enum class Outcome { Passthrough, Served, Fallback };
struct FontRedirect {
    AssetOpen original = nullptr;
    AAssetManager* replacements = nullptr;
    int64_t expected_size = 0;
    AAsset* open(AAssetManager* manager, const char* path, int mode, Outcome& outcome) const;
};
}
