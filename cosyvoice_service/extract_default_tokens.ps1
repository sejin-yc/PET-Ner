# 기본 토큰 추출 스크립트
# cosyvoice_service가 실행 중이어야 함 (docker compose up -d cosyvoice_service)
# 사용법: .\extract_default_tokens.ps1

$baseUrl = "http://localhost:50001"
$sampleDir = Join-Path $PSScriptRoot "sample_voices"
$outputDir = Join-Path $PSScriptRoot "..\server\src\main\resources\default_tokens"

$profiles = @(
    "male_10s", "male_20s", "male_30s", "male_40s", "male_50s",
    "female_10s", "female_20s", "female_30s", "female_40s", "female_50s"
)

foreach ($profile in $profiles) {
    $wavPath = Join-Path $sampleDir "$profile.wav"
    $promptPath = Join-Path $sampleDir "${profile}_prompt.txt"

    if (-not (Test-Path $wavPath)) {
        Write-Host "[SKIP] $profile - WAV 없음" -ForegroundColor Yellow
        continue
    }
    if (-not (Test-Path $promptPath)) {
        Write-Host "[SKIP] $profile - prompt 없음" -ForegroundColor Yellow
        continue
    }

    $prompt = (Get-Content $promptPath -Raw).Trim()
    $outputPath = Join-Path $outputDir "$profile.json"

    Write-Host "[추출] $profile ..." -ForegroundColor Cyan
    try {
        # curl.exe 사용 (Windows 10+ 내장)
        $curlOutput = & curl.exe -sS -w "`n%{http_code}" -X POST "$baseUrl/extract_tokens" `
            -F "prompt_text=$prompt" `
            -F "audio_file=@$wavPath" `
            -o $outputPath

        $lines = $curlOutput -split "`n"
        $statusCode = $lines[-1]
        if ($statusCode -eq "200") {
            Write-Host "  -> OK: $outputPath" -ForegroundColor Green
        } else {
            Write-Host "  -> 실패 (HTTP $statusCode)" -ForegroundColor Red
            if (Test-Path $outputPath) { Remove-Item $outputPath -Force }
        }
    } catch {
        Write-Host "  -> 오류: $_" -ForegroundColor Red
    }
}

# neutral.json 생성 (male_20s 복사)
$neutralPath = Join-Path $outputDir "neutral.json"
if (-not (Test-Path $neutralPath)) {
    $male20s = Join-Path $outputDir "male_20s.json"
    if (Test-Path $male20s) {
        Copy-Item $male20s $neutralPath
        Write-Host "`nneutral.json 생성 (male_20s 복사)" -ForegroundColor Gray
    }
}

Write-Host "`n완료." -ForegroundColor Gray
