# kit/common/sdk_program.cmake: how camlink (kit/link) and the editor's camera helper (kit/probe) are built against
# Sony's Camera Remote SDK for this OS, unpacked into kit/sdk/ by kit/setup.py (each OS has its own download). Each
# program's CMakeLists.txt includes this file before project(), so the macOS deployment target takes effect, then
# calls camset_sdk_program(<name> <source>).

set(CAMSET_COMMON ${CMAKE_CURRENT_LIST_DIR})
set(CAMSET_SDK_APP ${CMAKE_CURRENT_LIST_DIR}/../sdk/SimpleCli/app)
set(CAMSET_SDK_LIB ${CMAKE_CURRENT_LIST_DIR}/../sdk/SimpleCli/external/crsdk)

# The oldest macOS the SDK's own libraries run on (libCr_Core's minimum). It must be set before project(), which
# otherwise caches it empty, and the build then targets the macOS it runs on; a cache left empty by such a build is
# filled here. A value given with -D, or in the MACOSX_DEPLOYMENT_TARGET environment variable (which project() then
# takes), is kept.
if(CMAKE_HOST_APPLE AND NOT CMAKE_OSX_DEPLOYMENT_TARGET AND NOT DEFINED ENV{MACOSX_DEPLOYMENT_TARGET})
    set(CMAKE_OSX_DEPLOYMENT_TARGET "12.1" CACHE STRING "the oldest macOS the camera helpers run on" FORCE)
endif()
# Release unless asked (-D; env from CMake 3.22): Makefiles and Ninja build unoptimised without; --config is VS/Xcode's
get_property(CAMSET_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES AND NOT CAMSET_MULTI_CONFIG
   AND NOT (DEFINED ENV{CMAKE_BUILD_TYPE} AND CMAKE_VERSION VERSION_GREATER_EQUAL 3.22))
    set(CMAKE_BUILD_TYPE Release CACHE STRING "the camera helpers' build type (Release unless one is asked for)" FORCE)
endif()
# Visual Studio: the C runtime linked in, as Sony's samples build (no runtime DLL to ship beside the program)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

function(camset_sdk_program name source)
    add_executable(${name} ${source} ${CAMSET_SDK_APP}/CrDebugString.cpp)
    # kit/common: what the two programs share (camera_net.h: the network camera's address, MAC address, login and
    # fingerprint; sdk_session.h: the SDK's steps; callback_wait.h: the wait on the SDK's thread; never_touch.h,
    # written from kit/camkit/safety.py: what they never send; remote.h: the buttons and dials; sdk_values.h: a
    # property's value; settings_file.h: the check before an upload, and what camlink uploads; sha256.h: the hash it
    # checks those bytes by). The SDK's headers are system headers here, so the warnings below are the programs' own.
    target_include_directories(${name} PRIVATE ${CAMSET_COMMON})
    target_include_directories(${name} SYSTEM PRIVATE ${CAMSET_SDK_APP}/CRSDK ${CAMSET_SDK_APP})
    find_library(CR_CORE Cr_Core HINTS ${CAMSET_SDK_LIB} NO_DEFAULT_PATH REQUIRED)
    target_link_libraries(${name} PRIVATE ${CR_CORE})
    set_target_properties(${name} PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
    # warnings on, not fatal: a compiler newer than the one this was written with may find something new, and that
    # must not stop a build on someone's computer. Sony's CrDebugString.cpp is compiled as it comes, without them.
    # GCC and Clang only: Visual Studio's compilers (MSVC is true for clang-cl too, where -Wall means /Wall, every
    # warning there is) keep their default level, as Sony's samples build.
    if(NOT MSVC)
        target_compile_options(${name} PRIVATE -Wall -Wextra)
        set_source_files_properties(${CAMSET_SDK_APP}/CrDebugString.cpp PROPERTIES COMPILE_OPTIONS -w)
    endif()

    if(WIN32)
        # the SDK's strings are wchar_t on Windows, as in Sony's samples; kit/common/sdk_session.h converts
        target_compile_definitions(${name} PRIVATE UNICODE _UNICODE)
        # SendARP: the MAC address this computer's neighbour table holds for the camera's address (neighbourMac,
        # camera_net.h); CommandLineToArgvW: the camera helper's arguments as UTF-16 (camset_probe.cpp)
        target_link_libraries(${name} PRIVATE iphlpapi ws2_32 shell32)
        # the SDK DLLs and the CrAdapter folder sit next to the .exe
        add_custom_command(TARGET ${name} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_directory ${CAMSET_SDK_LIB} $<TARGET_FILE_DIR:${name}>)
    elseif(APPLE)
        set_target_properties(${name} PROPERTIES BUILD_RPATH "@executable_path")
        # On macOS the SDK loads its USB/LAN adapters from Contents/Frameworks/CrAdapter next to the executable.
        add_custom_command(TARGET ${name} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_directory ${CAMSET_SDK_LIB} $<TARGET_FILE_DIR:${name}>
            COMMAND ${CMAKE_COMMAND} -E make_directory $<TARGET_FILE_DIR:${name}>/Contents/Frameworks/CrAdapter
            COMMAND ${CMAKE_COMMAND} -E copy_directory ${CAMSET_SDK_LIB}/CrAdapter $<TARGET_FILE_DIR:${name}>/Contents/Frameworks/CrAdapter
            COMMAND ${CMAKE_COMMAND} -E rm -rf $<TARGET_FILE_DIR:${name}>/CrAdapter
            # the SDK dylibs arrive quarantined from the zip; Gatekeeper refuses them otherwise
            COMMAND xattr -dr com.apple.quarantine $<TARGET_FILE_DIR:${name}> || true)
    else()
        find_package(Threads REQUIRED)
        target_link_libraries(${name} PRIVATE Threads::Threads)
        target_compile_options(${name} PRIVATE -fsigned-char)          # as Sony's Linux samples build
        set_target_properties(${name} PROPERTIES BUILD_RPATH "$ORIGIN")
        # Cr_Core needs libxml2.so.2: a copy beside the SDK libraries (PORTING.md, Linux) is found here when linking,
        # via $ORIGIN when run
        target_link_options(${name} PRIVATE "-Wl,-rpath-link,${CAMSET_SDK_LIB}")
        add_custom_command(TARGET ${name} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_directory ${CAMSET_SDK_LIB} $<TARGET_FILE_DIR:${name}>)
    endif()
endfunction()
