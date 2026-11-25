cmake_minimum_required(VERSION 3.20)
project({{name}} CXX)

# ScriptHookV asi. Configure: cmake -S . -B build -G Ninja -DSHV_SDK=<sdk folder>  (gtaforge compile does this)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
if(NOT DEFINED SHV_SDK AND DEFINED ENV{SHV_SDK})
  set(SHV_SDK "$ENV{SHV_SDK}")
endif()
if(NOT EXISTS "${SHV_SDK}/inc/main.h")
  message(FATAL_ERROR "SHV_SDK must point at the ScriptHookV SDK (inc/main.h, lib/ScriptHookV.lib); got '${SHV_SDK}'")
endif()

add_library({{name}} SHARED src/main.cpp)
# inc/ first: its natives.h (gtaforge natives header) replaces the SDK's 2016 natives.h.
target_include_directories({{name}} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/inc" "${SHV_SDK}/inc")
target_link_libraries({{name}} PRIVATE "${SHV_SDK}/lib/ScriptHookV.lib")
target_compile_definitions({{name}} PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
if(MSVC)
  # Static CRT like the SDK samples: the asi needs no VC++ redistributable.
  set_property(TARGET {{name}} PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded")
  target_compile_options({{name}} PRIVATE /W4 /permissive- /utf-8)
endif()
set_target_properties({{name}} PROPERTIES OUTPUT_NAME "{{name}}" SUFFIX ".asi" PREFIX ""
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}" LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
