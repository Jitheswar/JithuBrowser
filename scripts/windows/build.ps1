<#
.SYNOPSIS  Build JithuBrowser for Windows x64 (run on Windows 10/11).
.NOTES
  Requirements (Chromium's official Windows build requirements):
    * Visual Studio 2022 with "Desktop development with C++", MFC/ATL and the
      Windows 11 SDK (with "Debugging Tools for Windows")
    * Git for Windows, Python 3 on PATH, ~150 GB free disk, 32 GB RAM
    * Long paths enabled:  git config --global core.longpaths true
  Google's prebuilt Windows toolchain is not available to the public, so
  DEPOT_TOOLS_WIN_TOOLCHAIN=0 makes the build use the local Visual Studio.
  Usage:  powershell -ExecutionPolicy Bypass -File scripts\windows\build.ps1
#>
param([string]$Work = "$PSScriptRoot\..\..\build-work", [int]$Jobs = [Environment]::ProcessorCount)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$Work = [IO.Path]::GetFullPath($Work)
$Version = (Get-Content "$Root\CHROMIUM_VERSION").Trim()
$env:DEPOT_TOOLS_WIN_TOOLCHAIN = "0"
$env:DEPOT_TOOLS_UPDATE = "0"
$env:vs2022_install = ${env:vs2022_install}
New-Item -ItemType Directory -Force "$Work\chromium" | Out-Null

if (-not (Test-Path "$Work\depot_tools")) {
  git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git "$Work\depot_tools"
}
$env:PATH = "$Work\depot_tools;$env:PATH"

Set-Location "$Work\chromium"
if (-not (Test-Path .gclient)) {
  @'
solutions = [{
  "name": "src",
  "url": "https://chromium.googlesource.com/chromium/src.git",
  "managed": False,
  "custom_deps": {},
  "custom_vars": {"checkout_nacl": False, "checkout_pgo_profiles": True},
}]
target_os = ["win"]
'@ | Set-Content .gclient
}
gclient sync --no-history --shallow --nohooks -j $Jobs --revision "src@refs/tags/$Version"
gclient runhooks -j $Jobs

Set-Location src
# Reset to pristine, then apply our patches.
git checkout -- . ; git -C v8 checkout -- . ; git -C third_party/devtools-frontend/src checkout -- .
Get-Content "$Root\patches\series" | Where-Object { $_ -and -not $_.StartsWith("#") } | ForEach-Object {
  Write-Host "applying $_"
  git apply --whitespace=nowarn --directory=. -p1 "$Root\patches\$_"
  if ($LASTEXITCODE) { throw "patch failed: $_" }
}
# Branding
$T = "chrome\app\theme\chromium"
(Get-Content "$T\BRANDING") `
  -replace '^COMPANY_FULLNAME=.*','COMPANY_FULLNAME=JithuBrowser Authors' `
  -replace '^COMPANY_SHORTNAME=.*','COMPANY_SHORTNAME=JithuBrowser Authors' `
  -replace '^PRODUCT_FULLNAME=.*','PRODUCT_FULLNAME=JithuBrowser' `
  -replace '^PRODUCT_SHORTNAME=.*','PRODUCT_SHORTNAME=JithuBrowser' `
  -replace '^PRODUCT_INSTALLER_FULLNAME=.*','PRODUCT_INSTALLER_FULLNAME=JithuBrowser Installer' `
  -replace '^PRODUCT_INSTALLER_SHORTNAME=.*','PRODUCT_INSTALLER_SHORTNAME=JithuBrowser Installer' |
  Set-Content "$T\BRANDING"
Copy-Item "$Root\branding\icons\jithubrowser.ico" "$T\win\chromium.ico" -Force
foreach ($s in 16,24,48,64,128,256) {
  foreach ($d in $T,"$T\linux") { if (Test-Path "$d\product_logo_$s.png") { Copy-Item "$Root\branding\icons\product_logo_$s.png" "$d\product_logo_$s.png" -Force } }
}

$Out = "out\JithuBrowser"
New-Item -ItemType Directory -Force $Out | Out-Null
Copy-Item "$Root\args.gn" "$Out\args.gn" -Force
Add-Content "$Out\args.gn" 'target_cpu = "x64"'
gn gen $Out
autoninja -C $Out -j $Jobs chrome chromedriver mini_installer
Write-Host "Build finished: $Work\chromium\src\$Out"
