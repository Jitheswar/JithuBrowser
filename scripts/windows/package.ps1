<#
.SYNOPSIS  Package a finished Windows build as a portable .zip and a setup .exe (Inno Setup 6).
#>
param([string]$Work = "$PSScriptRoot\..\..\build-work")
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$Out = [IO.Path]::GetFullPath("$Work\chromium\src\out\JithuBrowser")
$Ver = (Get-Content "$Root\CHROMIUM_VERSION").Trim() + "." + (Get-Content "$Root\JITHUBROWSER_REVISION").Trim()
$Dist = "$Root\dist"; New-Item -ItemType Directory -Force $Dist | Out-Null
$Stage = "$Dist\stage\JithuBrowser"
Remove-Item -Recurse -Force "$Dist\stage" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Stage | Out-Null

# Application files (everything the browser needs at runtime; no build intermediates)
Copy-Item "$Out\chrome.exe" "$Stage\jithubrowser.exe"
foreach ($f in "chrome_proxy.exe","chrome.dll","chrome_elf.dll","chrome_wer.dll","chrome_100_percent.pak","chrome_200_percent.pak",
               "resources.pak","icudtl.dat","v8_context_snapshot.bin","d3dcompiler_47.dll","libEGL.dll","libGLESv2.dll",
               "vk_swiftshader.dll","vk_swiftshader_icd.json","vulkan-1.dll","dxcompiler.dll","dxil.dll","chromedriver.exe") {
  if (Test-Path "$Out\$f") { Copy-Item "$Out\$f" $Stage }
}
foreach ($d in "locales","MEIPreload","WidevineCdm") { if (Test-Path "$Out\$d") { Copy-Item -Recurse "$Out\$d" $Stage } }
Get-ChildItem $Out -Directory | Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' } | ForEach-Object { Copy-Item -Recurse $_.FullName $Stage }
Copy-Item "$Root\LICENSE" "$Stage\LICENSE.JithuBrowser"

Compress-Archive -Path $Stage -DestinationPath "$Dist\jithubrowser-$Ver-windows-x64-portable.zip" -Force

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
  & $iscc "/DAppVersion=$Ver" "/DSourceDir=$Stage" "/DOutputDir=$Dist" "/DIconFile=$Root\branding\icons\jithubrowser.ico" "$Root\packaging\windows\jithubrowser.iss"
} else { Write-Warning "Inno Setup 6 not found; skipped installer. Install from https://jrsoftware.org/isinfo.php" }
Get-ChildItem $Dist -File | ForEach-Object { "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower())  $($_.Name)" } | Set-Content "$Dist\SHA256SUMS-windows.txt"
Write-Host "Done: $Dist"
