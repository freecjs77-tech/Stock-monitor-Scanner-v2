#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Magnificent 7 Daily Technical Analysis Report Generator
스케줄 태스크에서 자동 실행 — 매일 평일 오전 9시

실행 방법:
  python daily_mag7.py [--search]
  --search  웹 검색으로 최신 데이터 사용 (Claude 에이전트 환경에서만 작동)
  (기본값)  저장된 기본 데이터로 리포트 생성
"""

import sys, os, json, datetime
from pypdf import PdfWriter

# 리포트 엔진 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from report_engine import generate_report

REPORTS_DIR = os.path.join(SCRIPT_DIR, 'reports')
DATA_FILE   = os.path.join(SCRIPT_DIR, 'mag7_data.json')

# ══════════════════════════════════════════════════════════════════
#  기본 종목 데이터 (최신 검색값으로 업데이트 필요)
#  last_updated: 2026-03-20
# ══════════════════════════════════════════════════════════════════

DEFAULT_STOCKS = [
    {
        'ticker': 'NVDA', 'company': 'NVIDIA Corporation',
        'sector': 'AI / 반도체', 'exchange': 'NASDAQ',
        'close': 172.70, 'change_pct': -3.28,
        'high_52w': 212.19, 'low_52w': 86.62,
        'ma20': 183.98, 'ma50': 184.93, 'ma200': 178.28,
        'rsi': 47.33, 'macd': -1.37, 'macd_signal': -0.82,
        'bb_upper': 192.65, 'bb_lower': 179.05,
        'volume': 210e6, 'avg_volume': 185e6,
        'high_52w_date': '2025년 10월', 'low_52w_date': '2025년 4월',
        'opinion_note': '약세 지속',
        # 실제 가격 경로: 4월 저점→10월 고점→현재 하락
        'price_path': [(0,112),(25,86.62),(80,130),(145,212.19),(190,195),(220,178),(245,175),(261,172.70)],
    },
    {
        'ticker': 'PLTR', 'company': 'Palantir Technologies',
        'sector': 'AI / 방산 소프트웨어', 'exchange': 'NASDAQ',
        'close': 150.68, 'change_pct': -3.21,
        'high_52w': 207.51, 'low_52w': 126.23,
        'ma20': 138.50, 'ma50': 158.97, 'ma200': 161.80,
        'rsi': 41.5, 'macd': 2.85, 'macd_signal': 4.20,
        'bb_upper': 162.50, 'bb_lower': 114.50,
        'volume': 88e6, 'avg_volume': 60e6,
        'high_52w_date': '2025년 11월', 'low_52w_date': '2026년 1월',
        'opinion_note': '저항권 도달',
        # 실제 가격 경로: 꾸준한 상승→11월 고점→1월 급락→현재 반등
        'price_path': [(0,78),(50,95),(100,130),(170,207.51),(218,126.23),(240,138),(255,148),(261,150.68)],
    },
    {
        'ticker': 'TSLA', 'company': 'Tesla Inc.',
        'sector': 'EV / 에너지', 'exchange': 'NASDAQ',
        'close': 235.00, 'change_pct': -2.10,
        'high_52w': 479.86, 'low_52w': 138.80,
        'ma20': 258.50, 'ma50': 312.40, 'ma200': 290.00,
        'rsi': 38.5, 'macd': -8.20, 'macd_signal': -5.80,
        'bb_upper': 310.00, 'bb_lower': 207.00,
        'volume': 95e6, 'avg_volume': 110e6,
        'high_52w_date': '2025년 12월', 'low_52w_date': '2026년 2월',
        'opinion_note': '하락 추세',
        # 실제 가격 경로: 초반 고점→12월 재고점→급락→2월 저점→소폭 반등
        'price_path': [(0,260),(30,350),(60,290),(100,330),(196,479.86),(220,380),(240,138.80),(255,220),(261,235)],
    },
    {
        'ticker': 'AAPL', 'company': 'Apple Inc.',
        'sector': '소비자 전자기기', 'exchange': 'NASDAQ',
        'close': 213.49, 'change_pct': -1.20,
        'high_52w': 260.10, 'low_52w': 169.21,
        'ma20': 220.30, 'ma50': 232.80, 'ma200': 225.50,
        'rsi': 44.2, 'macd': -2.85, 'macd_signal': -1.90,
        'bb_upper': 248.60, 'bb_lower': 191.90,
        'volume': 58e6, 'avg_volume': 62e6,
        'high_52w_date': '2025년 12월', 'low_52w_date': '2025년 4월',
        'opinion_note': '중립 관망',
        # 실제 가격 경로: 4월 저점→완만한 상승→12월 고점→현재 하락
        'price_path': [(0,185),(25,169.21),(80,200),(140,220),(196,260.10),(225,245),(245,225),(261,213.49)],
    },
    {
        'ticker': 'MSFT', 'company': 'Microsoft Corporation',
        'sector': '클라우드 / AI 플랫폼', 'exchange': 'NASDAQ',
        'close': 388.45, 'change_pct': -0.85,
        'high_52w': 468.35, 'low_52w': 344.79,
        'ma20': 395.20, 'ma50': 418.60, 'ma200': 421.30,
        'rsi': 46.8, 'macd': -5.40, 'macd_signal': -3.20,
        'bb_upper': 440.00, 'bb_lower': 350.40,
        'volume': 22e6, 'avg_volume': 24e6,
        'high_52w_date': '2025년 7월', 'low_52w_date': '2026년 3월',
        'opinion_note': '중립/약세',
        # 실제 가격 경로: 완만한 상승→7월 고점→완만한 장기 하락→현재 52주 저점
        'price_path': [(0,380),(40,410),(85,468.35),(130,450),(180,435),(220,415),(245,395),(261,388.45)],
    },
    {
        'ticker': 'GOOGL', 'company': 'Alphabet Inc.',
        'sector': '검색 / 클라우드 / AI', 'exchange': 'NASDAQ',
        'close': 162.80, 'change_pct': -1.55,
        'high_52w': 208.70, 'low_52w': 140.53,
        'ma20': 168.40, 'ma50': 182.90, 'ma200': 183.60,
        'rsi': 43.5, 'macd': -2.10, 'macd_signal': -1.40,
        'bb_upper': 192.00, 'bb_lower': 144.80,
        'volume': 28e6, 'avg_volume': 30e6,
        'high_52w_date': '2025년 11월', 'low_52w_date': '2026년 1월',
        'opinion_note': '중립 관망',
        # 실제 가격 경로: 저점→꾸준한 상승→11월 고점→1월 급락→현재 회복
        'price_path': [(0,155),(25,140.53),(80,165),(140,185),(170,208.70),(218,142),(240,155),(261,162.80)],
    },
    {
        'ticker': 'AMZN', 'company': 'Amazon.com Inc.',
        'sector': '이커머스 / 클라우드', 'exchange': 'NASDAQ',
        'close': 196.30, 'change_pct': -1.80,
        'high_52w': 242.52, 'low_52w': 161.02,
        'ma20': 202.60, 'ma50': 218.40, 'ma200': 214.80,
        'rsi': 45.1, 'macd': -3.20, 'macd_signal': -2.10,
        'bb_upper': 230.00, 'bb_lower': 175.20,
        'volume': 42e6, 'avg_volume': 45e6,
        'high_52w_date': '2026년 2월', 'low_52w_date': '2025년 4월',
        'opinion_note': '중립 관망',
        # 실제 가격 경로: 4월 저점→꾸준한 장기 상승→2월 고점→최근 급락
        'price_path': [(0,175),(25,161.02),(70,185),(130,205),(185,225),(240,242.52),(255,215),(261,196.30)],
    },
    {
        'ticker': 'META', 'company': 'Meta Platforms Inc.',
        'sector': 'SNS / AI 광고', 'exchange': 'NASDAQ',
        'close': 578.20, 'change_pct': -2.30,
        'high_52w': 740.91, 'low_52w': 475.32,
        'ma20': 605.40, 'ma50': 648.80, 'ma200': 620.50,
        'rsi': 42.8, 'macd': -12.50, 'macd_signal': -8.30,
        'bb_upper': 680.00, 'bb_lower': 530.80,
        'volume': 16e6, 'avg_volume': 18e6,
        'high_52w_date': '2026년 1월', 'low_52w_date': '2025년 4월',
        'opinion_note': '중립/약세',
        # 실제 가격 경로: 4월 저점→꾸준한 가파른 상승→1월 고점→최근 급락
        'price_path': [(0,520),(25,475.32),(80,550),(140,620),(200,700),(218,740.91),(240,650),(261,578.20)],
    },
]


def load_stock_data():
    """mag7_data.json 있으면 로드, 없으면 DEFAULT 사용"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"  [data] Loaded from {DATA_FILE} (updated: {data.get('last_updated', 'unknown')})")
        return data['stocks']
    print("  [data] Using default stock data (run with --search to update)")
    return DEFAULT_STOCKS


def merge_pdfs(pdf_paths, output_path):
    """개별 PDF들을 하나의 파일로 병합"""
    writer = PdfWriter()
    for path in pdf_paths:
        writer.append(path)
    with open(output_path, 'wb') as f:
        writer.write(f)
    writer.close()


def run():
    today     = datetime.date.today().strftime('%Y-%m-%d')
    today_str = datetime.date.today().strftime('%Y%m%d')
    print(f"\n{'='*55}")
    print(f"  Mag7 Daily Technical Analysis  |  {today}")
    print(f"{'='*55}")

    stocks = load_stock_data()
    generated = []
    tmp_dir = os.path.join(REPORTS_DIR, '_tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    for sd in stocks:
        ticker = sd['ticker']
        print(f"\n  [{ticker}] Generating report...")
        try:
            path = generate_report(sd, tmp_dir)
            generated.append((ticker, path))
            print(f"  [{ticker}] OK")
        except Exception as e:
            print(f"  [{ticker}] ERROR: {e}")

    # 개별 PDF들을 하나로 병합
    merged_path = os.path.join(REPORTS_DIR, f'Mag7_Daily_Report_{today_str}.pdf')
    if generated:
        pdf_paths = [path for _, path in generated]
        print(f"\n  [MERGE] Combining {len(pdf_paths)} reports...")
        merge_pdfs(pdf_paths, merged_path)
        print(f"  [MERGE] OK -> {os.path.basename(merged_path)}")

        # 임시 개별 파일 삭제
        for path in pdf_paths:
            try: os.remove(path)
            except: pass
        try: os.rmdir(tmp_dir)
        except: pass

    # 완료 요약 파일 (telegram_sender.py 트리거용)
    summary_path = os.path.join(REPORTS_DIR, f'daily_summary_{today}.txt')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"generated_date={today}\n")
        f.write(f"merged={merged_path}\n")
        for ticker, _ in generated:
            f.write(f"{ticker}=OK\n")

    print(f"\n  [DONE] {len(generated)}/{len(stocks)} reports → {os.path.basename(merged_path)}")
    return merged_path


if __name__ == '__main__':
    run()
