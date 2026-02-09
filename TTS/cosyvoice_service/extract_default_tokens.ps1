# 기본 토큰 추출 스크립트
# cosyvoice_service가 실행 중이어야 함 (docker compose up -d cosyvoice_service)
# 사용법: .\extract_default_tokens.ps1

$baseUrl = "http://127.0.0.1:50001"
$sampleDir = Join-Path $PSScriptRoot "sample_voices"
$outputDir = Join-Path $PSScriptRoot "..\server\src\main\resources\default_tokens"
$requestTimeoutSec = 600   # 프로필당 최대 10분 (토큰 추출은 2~5분 소요 가능)

$profiles = @(
    "male_10s", "male_20s", "male_30s", "male_40s", "male_50s",
    "female_10s", "female_20s", "female_30s", "female_40s", "female_50s"
)

# 서비스 준비 대기 (컨테이너 재시작 직후 모델 로딩 5~10분 소요 가능)
# Invoke-WebRequest는 Windows에서 localhost/타임아웃 이슈 있을 수 있어 curl.exe 사용
$healthUrl = "http://127.0.0.1:50001/health"
Write-Host "서비스 준비 확인 중... ($healthUrl)" -ForegroundColor Gray
$maxWait = 900   # 최대 15분 대기
$waited = 0
while ($waited -lt $maxWait) {
    try {
        $code = curl.exe -sS -o NUL -w "%{http_code}" --connect-timeout 5 --max-time 10 "$healthUrl"
        if ($code -eq "200") {
            Write-Host "서비스 준비 완료 (${waited}초 후)" -ForegroundColor Green
            break
        }
    } catch {
        # curl 실패 시에도 진행
    }
    Start-Sleep -Seconds 10
    $waited += 10
    Write-Host "  대기 중... ${waited}초 (docker logs cosyvoice_service 로 모델 로딩 확인)" -ForegroundColor Yellow
}
if ($waited -ge $maxWait) {
    Write-Host "서비스가 준비되지 않았습니다. docker logs cosyvoice_service 를 확인하세요." -ForegroundColor Red
    Write-Host "수동 확인: curl.exe -s $healthUrl" -ForegroundColor Gray
    exit 1
}

Write-Host "프로필당 최대 ${requestTimeoutSec}초 타임아웃 (2~5분 소요 가능)" -ForegroundColor Gray
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

    Write-Host "[추출] $profile ... (약 2~5분 소요)" -ForegroundColor Cyan
    try {
        # curl.exe 사용 (Windows 10+ 내장), --max-time: 무한 대기 방지
        $curlOutput = & curl.exe -sS -w "`n%{http_code}" --max-time $requestTimeoutSec `
            -X POST "$baseUrl/extract_tokens" `
            -F "prompt_text=$prompt" `
            -F "audio_file=@$wavPath" `
            -o $outputPath

        if ($LASTEXITCODE -eq 28) {
            Write-Host "  -> 타임아웃 (${requestTimeoutSec}초 초과)" -ForegroundColor Red
            if (Test-Path $outputPath) { Remove-Item $outputPath -Force }
            continue
        }

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
