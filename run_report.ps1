Set-Location "C:\Users\DIT-969\mag7-stock-report"

Write-Host "=== deep-translator 설치 ===" -ForegroundColor Cyan
python -m pip install deep-translator --quiet

Write-Host "`n=== 리포트 생성 시작 ===" -ForegroundColor Cyan
python local_mag7_real.py

Write-Host "`n=== PDF 파일 열기 ===" -ForegroundColor Cyan
$reportDir = "C:\Users\DIT-969\mag7-stock-report\cowork_agents\reports"
$latest = Get-ChildItem "$reportDir\Mag7_Daily_Report_*.pdf" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($latest) {
    Write-Host "열기: $($latest.FullName)" -ForegroundColor Green
    Start-Process $latest.FullName
} else {
    Write-Host "PDF 파일을 찾을 수 없습니다." -ForegroundColor Red
}
