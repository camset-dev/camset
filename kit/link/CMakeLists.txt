cmake_minimum_required(VERSION 3.16)
# how both camera helpers build against Sony's Camera Remote SDK (kit/sdk/), per OS: Sony's samples' settings (UNICODE
# and the static MSVC runtime on Windows, the CrAdapter folder on macOS, threads, -fsigned-char and the $ORIGIN and
# -rpath-link paths on Linux), the SDK's libraries copied beside the program. Before project(): the macOS target.
include(${CMAKE_CURRENT_LIST_DIR}/../common/sdk_program.cmake)
project(camlink LANGUAGES CXX)

# camlink: the kit's camera link (kit/camkit/link.py); protocol.h, its command lines, sits beside it
camset_sdk_program(camlink camlink.cpp)
# importlut takes a user LUT from this clone's own private/lut/ alone (docs/decisions/0026): the folder built in, made
# absolute here; camlink follows it to where it really is, and refuses every import while it is not there
get_filename_component(CAMSET_CLONE_LUT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../private/lut" ABSOLUTE)
target_compile_definitions(camlink PRIVATE "CAMSET_LUT_DIR=\"${CAMSET_CLONE_LUT_DIR}\"")
