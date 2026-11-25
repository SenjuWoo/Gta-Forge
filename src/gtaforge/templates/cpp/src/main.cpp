// {{name}} - ScriptHookV asi. Story mode only: ScriptHookV closes the game in GTA Online.
#include "main.h"     // SDK: scriptRegister, WAIT, keyboard and texture helpers
#include "types.h"    // SDK: Ped, Vehicle, Vector3, ...
#include "natives.h"  // inc/natives.h: current native DB (gtaforge natives header)

// Natives run only inside a script ScriptHookV registered (a fiber on the game's script thread).
// Never call one from a thread you created yourself.
static void ScriptMain()
{
    for (;;)
    {
        const Ped player = PLAYER::PLAYER_PED_ID();
        if (ENTITY::DOES_ENTITY_EXIST(player) && !ENTITY::IS_ENTITY_DEAD(player, FALSE))
        {
            // Your per-frame logic here. Check handles before use.
        }
        WAIT(0);
    }
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID)
{
    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
        scriptRegister(module, ScriptMain);
        break;
    case DLL_PROCESS_DETACH:
        scriptUnregister(module);
        break;
    }
    return TRUE;
}
