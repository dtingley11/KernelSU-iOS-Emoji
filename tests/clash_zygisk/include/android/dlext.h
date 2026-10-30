#pragma once
#include <cstdint>
#define ANDROID_DLEXT_USE_LIBRARY_FD 0x10
struct android_dlextinfo { uint64_t flags; int library_fd; };
extern "C" void* android_dlopen_ext(const char*, int, const android_dlextinfo*);
