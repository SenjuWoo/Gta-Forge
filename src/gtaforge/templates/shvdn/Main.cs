// {{name}} - SHVDN3 script. Single-player only.
using GTA;
using GTA.Native;

public class Main : Script
{
    public Main()
    {
        Tick += OnTick;
    }

    private void OnTick(object sender, System.EventArgs e)
    {
        Ped player = Game.Player.Character;
        if (player == null || !player.Exists()) return;
        // Your logic here.
    }
}