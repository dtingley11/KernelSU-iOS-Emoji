#include "font_redirect.h"
#include "core.h"
#include <cstring>

namespace clash_font {
AAsset* FontRedirect::open(AAssetManager* manager, const char* path, int mode, Outcome& outcome) const {
    outcome = Outcome::Passthrough;
    if (!original) return nullptr;
    if (!replacements || manager == replacements || !path || std::strcmp(path, target_path) != 0) {
        return original(manager, path, mode);
    }
    AAsset* asset = original(replacements, replacement_path, mode);
    if (asset && expected_size > 0 && AAsset_getLength64(asset) == expected_size) {
        outcome = Outcome::Served;
        return asset;
    }
    if (asset) AAsset_close(asset);
    outcome = Outcome::Fallback;
    return original(manager, path, mode);
}
}
