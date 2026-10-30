#pragma once
#include <cstdint>
struct AAssetManager;
struct AAsset;
extern "C" int64_t AAsset_getLength64(AAsset* asset);
extern "C" void AAsset_close(AAsset* asset);
