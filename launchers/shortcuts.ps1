# Makes the SC Inventory Tracker shortcuts, with their icons.
# Setup.bat runs this. Run Setup.bat again if you move the tracker folder.
#   -Extra   also add a Start menu folder and two desktop shortcuts
param([switch]$Extra)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$icons = Join-Path $root 'sctracker\assets'
$shell = New-Object -ComObject WScript.Shell
$items = @(
  @{ Name = 'SC Inventory Tracker';              Bat = 'tracker.bat';            Icon = 'tracker.ico';   Desc = 'Track your station storage while you play' },
  @{ Name = 'SC Inventory Dashboard';            Bat = 'dashboard.bat';          Icon = 'dashboard.ico'; Desc = 'Look up what you have stored, and where' },
  @{ Name = 'SC Inventory Tracker (no overlay)'; Bat = 'tracker-no-overlay.bat'; Icon = 'tracker.ico';   Desc = 'Track your storage without the on-screen markers' },
  @{ Name = 'SC Inventory Screenshot Reader';    Bat = 'read-screenshots.bat';   Icon = 'tracker.ico';   Desc = 'Read storage kiosk screenshots you took in game' }
)

function New-Shortcut($dir, $it) {
  $lnk = $shell.CreateShortcut((Join-Path $dir ($it.Name + '.lnk')))
  $lnk.TargetPath = $env:ComSpec
  $lnk.Arguments = '/c "' + (Join-Path $root ('launchers\' + $it.Bat)) + '"'
  $lnk.WorkingDirectory = $root
  $lnk.IconLocation = (Join-Path $icons $it.Icon) + ',0'
  $lnk.Description = $it.Desc
  $lnk.Save()
}

foreach ($it in $items) { New-Shortcut $root $it }
Write-Host 'Shortcuts made in the tracker folder.'

if ($Extra) {
  $menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'SC Inventory Tracker'
  New-Item -ItemType Directory -Force -Path $menu | Out-Null
  foreach ($it in $items) { New-Shortcut $menu $it }
  $desk = [Environment]::GetFolderPath('Desktop')
  New-Shortcut $desk $items[0]
  New-Shortcut $desk $items[1]
  Write-Host 'Added a Start menu folder and desktop shortcuts for the tracker and the dashboard.'
}
