-- {{name}} client (FiveM). Natives via Citizen.InvokeNative.
Citizen.CreateThread(function()
  while true do
    Citizen.Wait(0)
    local ped = PlayerPedId()
    if DoesEntityExist(ped) then
      -- Your logic here.
    end
  end
end)