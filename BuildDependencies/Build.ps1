param(
    [switch]$Run
)

$ErrorActionPreference = "Stop"

$buildToolsDirectory = Join-Path $env:LOCALAPPDATA "RA2CC4\BuildTools"
$dotnetDirectory = Join-Path $buildToolsDirectory "dotnet"
$localDotnet = Join-Path $dotnetDirectory "dotnet.exe"
$installerScript = Join-Path $buildToolsDirectory "dotnet-install.ps1"
New-Item -ItemType Directory -Path $buildToolsDirectory -Force | Out-Null

$installedSdks = @()
if (Test-Path -LiteralPath $localDotnet) {
    $installedSdks = & $localDotnet --list-sdks
}
if (-not ($installedSdks | Where-Object { $_ -match '^8\.' })) {
    New-Item -ItemType Directory -Path $buildToolsDirectory -Force | Out-Null
    Invoke-WebRequest -Uri "https://dot.net/v1/dotnet-install.ps1" -OutFile $installerScript
    & $installerScript -Channel 8.0 -InstallDir $dotnetDirectory -Architecture x64 -NoPath
    if (-not (Test-Path -LiteralPath $localDotnet)) { throw "The .NET 8 SDK installation failed." }
    $installedSdks = & $localDotnet --list-sdks
    if ($LASTEXITCODE -ne 0 -or -not ($installedSdks | Where-Object { $_ -match '^8\.' })) {
        throw "The .NET 8 SDK installation could not be verified."
    }
}

$env:DOTNET_ROOT = $dotnetDirectory
$env:PATH = "$dotnetDirectory;$env:PATH"
$env:NUGET_PACKAGES = Join-Path $buildToolsDirectory "nuget-packages"
$project = Join-Path $PSScriptRoot "..\WinUIFrontend\RA2CC4.csproj"
$nugetConfig = Join-Path $PSScriptRoot "NuGet.Config"

if ($Run) {
    $publicRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
    $outputDirectory = [IO.Path]::GetFullPath((Join-Path $publicRoot "Output"))
    if ([IO.Path]::GetFullPath((Split-Path -Parent $outputDirectory)) -ne $publicRoot -or (Split-Path -Leaf $outputDirectory) -ne "Output") {
        throw "Invalid public output directory."
    }
    if (Test-Path -LiteralPath $outputDirectory) {
        Get-ChildItem -LiteralPath $outputDirectory -Force | Remove-Item -Recurse -Force
    }
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    & $localDotnet publish $project -c Publish -r win-x64 --self-contained true `
        -p:WindowsAppSDKSelfContained=true -p:EnableMsixTooling=true `
        -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true `
        -p:EnableCompressionInSingleFile=true -p:PublishTrimmed=false -p:RestoreConfigFile=$nugetConfig `
        -p:NoWarn=NETSDK1244 -p:DebugType=None -p:DebugSymbols=false -o $outputDirectory
    if ($LASTEXITCODE -ne 0) { throw "The single-file publish failed with exit code $LASTEXITCODE." }
    $application = Join-Path $outputDirectory "RA2CC4.exe"
    if (-not (Test-Path -LiteralPath $application)) { throw "The public build did not create RA2CC4.exe in Output." }
    $extraFiles = @(Get-ChildItem -LiteralPath $outputDirectory -Force -Recurse | Where-Object { $_.FullName -ne $application })
    if ($extraFiles.Count -gt 0) { throw "The public build produced files outside the single executable." }
    & $application
    if ($LASTEXITCODE -ne 0) { throw "The application exited with code $LASTEXITCODE." }
    exit 0
}

$distributionScript = Join-Path $PSScriptRoot "..\build-distribution.ps1"
& $distributionScript
