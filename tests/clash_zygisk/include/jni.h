#pragma once
#include <cstdint>
#include <string>
using jint = int;
using jsize = int;
using jchar = uint16_t;
using jstring = const std::u16string*;
struct JNIEnv {
    bool exception = false;
    bool ExceptionCheck() { return exception; }
    void ExceptionClear() { exception = false; }
    jsize GetStringLength(jstring name) { return static_cast<jsize>(name->size()); }
    void GetStringRegion(jstring name, jsize start, jsize count, jchar* output) {
        for (jsize i = 0; i < count; ++i) output[i] = (*name)[start + i];
    }
};
