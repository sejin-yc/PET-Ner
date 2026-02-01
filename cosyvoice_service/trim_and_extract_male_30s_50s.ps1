# male_30s, male_50s용 오디오 25초로 자르고 토큰 추출
# CosyVoice는 30초 초과 오디오 토큰 추출 미지원
# 사용법: .\trim_and_extract_male_30s_50s.ps1

$sampleDir = Join-Path $PSScriptRoot "sample_voices"
$outputDir = Join-Path $PSScriptRoot "..\server\src\main\resources\default_tokens"
$baseUrl = "http://localhost:50001"

# 25초로 잘린 오디오에 맞는 짧은 프롬프트 (원본의 앞부분)
$shortPrompts = @{
    male_30s = "내 주변 사람들은 애완동물을 키우지 않거나 키우더라도 다들 강아지만 키운다고 하더라고. 물론 강아지가 충성심이 강하다고해서 매력있는걸 알지만 고양이도 무지 커여운걸? 아무래도 다들 냥냥이가 꾹꾹이하는 행동을 보지 못해서 그런것 같아."
    male_50s = "내 주변 사람들은 애완동물을 키우지 않거나 키우더라도 다들 강아지만 키운다고 하더라고. 물론 강아지가 충성심이 강하다고해서 매력있는걸 알지만 고양이도 무지 커여운걸? 아무래도 다들 냥냥이가 꾹꾹이하는 행동을 보지 못해서 그런것 같아."
}

foreach ($profile in @("male_30s", "male_50s")) {
    $wavPath = Join-Path $sampleDir "$profile.wav"
    $trimmedPath = Join-Path $sampleDir "${profile}_trimmed.wav"

    if (-not (Test-Path $wavPath)) {
        Write-Host "[SKIP] $profile.wav 없음" -ForegroundColor Yellow
        continue
    }

    Write-Host "[1/2] $profile - 오디오 25초로 자르는 중..." -ForegroundColor Cyan
    & ffmpeg -y -i $wavPath -t 25 -ac 1 -ar 16000 $trimmedPath 2>$null
    if (-not (Test-Path $trimmedPath)) {
        Write-Host "  ffmpeg 실패 (ffmpeg 설치 확인)" -ForegroundColor Red
        continue
    }

    Write-Host "[2/2] $profile - 토큰 추출 중..." -ForegroundColor Cyan
    $prompt = $shortPrompts[$profile]
    $outPath = Join-Path $outputDir "$profile.json"
    $curlOut = & curl.exe -sS -w "`n%{http_code}" -X POST "$baseUrl/extract_tokens" `
        -F "prompt_text=$prompt" `
        -F "audio_file=@$trimmedPath" `
        -o $outPath 2>&1

    $code = ($curlOut -split "`n")[-1]
    if ($code -eq "200") {
        Write-Host "  -> OK: $outPath" -ForegroundColor Green
    } else {
        Write-Host "  -> 실패 (HTTP $code)" -ForegroundColor Red
        if (Test-Path $outPath) { Remove-Item $outPath -Force }
    }

    if (Test-Path $trimmedPath) { Remove-Item $trimmedPath -Force }
}

Write-Host "`n완료. 프롬프트가 잘린 오디오와 안 맞으면 male_30s_prompt.txt 앞부분을 듣고 맞게 수정 후 재실행하세요." -ForegroundColor Gray
