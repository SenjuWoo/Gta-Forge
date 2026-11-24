// {{name}} - ScriptHookV asi. Single-player only.
#include "main.h"
#include <windows.h>

BOOL APIENTRY DllMain(HMODULE h, DWORD reason, LPVOID) {
  if (reason == DLL_PROCESS_ATTACH) {
    DisableThreadLibraryCalls(h);
    CreateThread(nullptr, 0, [](LPVOID) -> DWORD {
      while (true) {
        WAIT(0);
        Ped player = PLAYER_PED_ID();
        if (!DOES_ENTITY_EXIST(player)) continue;
        // Your logic here. Never call a native on an invalid handle.
      }
    }, nullptr, 0, nullptr);
  }
  return TRUE;
}