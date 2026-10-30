#include "font_redirect.h"
#include <cassert>
#include <cstring>
#include <iostream>

struct AAssetManager {};
struct AAsset { int64_t size; bool closed; };
static AAssetManager game, replacement;
static AAsset stock{100, false}, ios{200, false};
static bool missing = false;
static unsigned calls = 0;
static int last_mode = -1;
static AAssetManager* last_manager = nullptr;
static const char* last_path = nullptr;

extern "C" int64_t AAsset_getLength64(AAsset* asset) { return asset->size; }
extern "C" void AAsset_close(AAsset* asset) { asset->closed = true; }

static AAsset* original(AAssetManager* manager, const char* path, int mode) {
    ++calls;
    last_mode = mode;
    last_manager = manager;
    last_path = path;
    if (manager == &replacement && path && std::strcmp(path, "replacement.ttf") == 0) {
        return missing ? nullptr : &ios;
    }
    return &stock;
}

int main() {
    using clash_font::Outcome;
    clash_font::FontRedirect redirect{original, &replacement, 200};
    Outcome outcome;
    const char* target = "titan/fonts/NotoColorEmoji.ttf";
    const char* other_paths[] = {"other.ttf", "titan/fonts/NotoColorEmoji.ttf.bak",
                                "assets/titan/fonts/NotoColorEmoji.ttf", "replacement.ttf", "", nullptr};
    for (const char* path : other_paths) {
        calls = 0;
        assert(redirect.open(&game, path, 2, outcome) == &stock);
        assert(outcome == Outcome::Passthrough && calls == 1 && last_mode == 2);
        assert(last_manager == &game && last_path == path);
    }
    for (int mode = 0; mode < 4; ++mode) {
        calls = 0;
        assert(redirect.open(&game, target, mode, outcome) == &ios);
        assert(outcome == Outcome::Served && calls == 1 && last_mode == mode && !ios.closed);
        assert(last_manager == &replacement && std::strcmp(last_path, "replacement.ttf") == 0);
    }
    calls = 0;
    assert(redirect.open(&replacement, target, 1, outcome) == &stock);
    assert(outcome == Outcome::Passthrough && calls == 1);
    missing = true;
    calls = 0;
    assert(redirect.open(&game, target, 3, outcome) == &stock);
    assert(outcome == Outcome::Fallback && calls == 2 && last_mode == 3 && !ios.closed);
    assert(last_manager == &game && last_path == target);
    missing = false;
    ios.size = 201;
    calls = 0;
    assert(redirect.open(&game, target, 0, outcome) == &stock);
    assert(outcome == Outcome::Fallback && ios.closed && calls == 2);
    assert(last_manager == &game && last_path == target);
    ios = {200, false};
    redirect.expected_size = 0;
    assert(redirect.open(&game, target, 1, outcome) == &stock);
    assert(outcome == Outcome::Fallback && ios.closed);
    redirect.replacements = nullptr;
    calls = 0;
    assert(redirect.open(&game, target, 1, outcome) == &stock);
    assert(outcome == Outcome::Passthrough && calls == 1);
    redirect.original = nullptr;
    assert(redirect.open(&game, target, 1, outcome) == nullptr);
    std::cout << "Native font redirection cases passed\n";
}
