-- {{name}} server (FiveM)
AddEventHandler('playerJoining', function()
  local src = source
  print(('[%s] %s joined'):format('{{name}}', src))
end)