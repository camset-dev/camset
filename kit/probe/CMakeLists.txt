cmake_minimum_required(VERSION 3.16)
# how both camera helpers build against Sony's Camera Remote SDK (kit/sdk/), per OS: Sony's samples' settings (UNICODE
# and the static MSVC runtime on Windows, the CrAdapter folder on macOS, threads, -fsigned-char and the $ORIGIN and
# -rpath-link paths on Linux), the SDK's libraries copied beside the program. Before project(): the macOS target.
include(${CMAKE_CURRENT_LIST_DIR}/../common/sdk_program.cmake)
project(camset_probe LANGUAGES CXX)

# camset_probe: the editor's camera helper (discover, list, download, upload)
camset_sdk_program(camset_probe camset_probe.cpp)
