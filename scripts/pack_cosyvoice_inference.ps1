# CosyVoice "추론만" 패키징 스크립트
# Jetson에 올릴 때 토큰 추출 없이 TTS 추론에 필요한 cosyvoice 코드만 zip으로 묶습니다.
#
# 사용법: CV3-test 루트에서 실행
#   cd c:\Users\SSAFY\downtown\mingsung\CV3-test
#   .\S14P11C203\scripts\pack_cosyvoice_inference.ps1
#
# 또는 스크립트만 실행 (스크립트 위치 기준으로 상위 폴더를 repo 루트로 사용)
#   .\S14P11C203\scripts\pack_cosyvoice_inference.ps1

$ErrorActionPreference = "Stop"

# Repo 루트 = 스크립트 기준 상위 두 단계 (S14P11C203/scripts -> S14P11C203 -> CV3-test)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$CosyVoiceSrc = Join-Path $RepoRoot "CosyVoice\cosyvoice"
$ZipName = "CosyVoice_inference_only.zip"
$ZipPath = Join-Path $RepoRoot $ZipName

if (-not (Test-Path $CosyVoiceSrc)) {
    Write-Error "CosyVoice 소스가 없습니다: $CosyVoiceSrc"
}

$TempDir = Join-Path $env:TEMP "CosyVoice_inference_bundle"
$DestCosy = Join-Path $TempDir "CosyVoice\cosyvoice"

if (Test-Path $TempDir) {
    Remove-Item -Recurse -Force $TempDir
}
New-Item -ItemType Directory -Force -Path $DestCosy | Out-Null

# bin, dataset, vllm, __pycache__ 제외하고 복사 (robocopy 사용)
& robocopy $CosyVoiceSrc $DestCosy /E /XD bin dataset vllm __pycache__ /NFL /NDL /NJH /NJS /NC /NS
if ($LASTEXITCODE -ge 8) {
    Write-Error "robocopy 실패: $LASTEXITCODE"
}

# 압축 (기존 zip 있으면 덮어쓰기)
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
$CosyVoiceFolder = Join-Path $TempDir "CosyVoice"
Compress-Archive -Path $CosyVoiceFolder -DestinationPath $ZipPath -Force

Remove-Item -Recurse -Force $TempDir

Write-Host "Done: $ZipPath"
Write-Host "Unzip to get CosyVoice/cosyvoice/. On Jetson add CosyVoice to sys.path."
