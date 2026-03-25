#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quick_render.py — 캐시 데이터로 PDF 즉시 재생성 (네트워크 없음)

사용법:
    python quick_render.py              # 캐시된 전 종목 재렌더
    python quick_render.py NVDA         # 특정 종목만
    python quick_render.py NVDA GOOGL   # 여러 종목
    python quick_render.py --open       # 생성 후 자동 열기
    python quick_render.py NVDA --open  # 특정 종목 + 자동 열기
"""

import os, sys, json, datetime, tempfile, subprocess
from pypdf import PdfWriter

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR  = os.path.join(SCRIPT_DIR, 'cowork_agents')
REPORTS_DIR = os.path.join(AGENTS_DIR, 'reports')
DATA_FILE   = os.path.join(AGENTS_DIR, 'mag7_data.json')

sys.path.insert(0, AGENTS_DIR)
from report_engine import generate_report, generate_summary_page


def load_cache(tickers=None):
    """mag7_data.json 에서 종목 데이터 로드"""
    if not os.path.exists(DATA_FILE):
        print(f"[ERROR] 캐시 파일 없음: {DATA_FILE}")
        print("        먼저 local_mag7_real.py 를 실행해서 데이터를 받아주세요.")
        sys.exit(1)

    with open(DATA_FILE, encoding='utf-8') as f:
        cache = json.load(f)

    stocks = cache.get('stocks', [])
    updated = cache.get('last_updated', '?')
    print(f"  [CACHE] {updated} 기준 데이터 사용 ({len(stocks)}개 종목)")

    if tickers:
        stocks = [s for s in stocks if s['ticker'] in tickers]
        missing = set(tickers) - {s['ticker'] for s in stocks}
        if missing:
            print(f"  [WARN]  캐시에 없는 종목: {', '.join(missing)}")

    return stocks


def merge_pdfs(pdf_paths, output_path):
    writer = PdfWriter()
    for p in pdf_paths:
        writer.append(p)
    with open(output_path, 'wb') as f:
        writer.write(f)
    writer.close()


def open_pdf(path):
    """OS에 맞게 PDF 열기"""
    try:
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])
    except Exception as e:
        print(f"  [WARN] 자동 열기 실패: {e}")


def run(tickers=None, auto_open=False):
    today_str = datetime.date.today().strftime('%Y%m%d')

    print(f"\n{'='*55}")
    print(f"  Quick Render  |  캐시 데이터 사용 (네트워크 없음)")
    print(f"{'='*55}")

    stocks = load_cache(tickers)
    if not stocks:
        print("[ERROR] 렌더할 데이터 없음.")
        sys.exit(1)

    ticker_list = [s['ticker'] for s in stocks]
    print(f"  대상 종목: {' / '.join(ticker_list)}\n")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    tmp_dir = os.path.join(REPORTS_DIR, '_tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    generated = []
    for sd in stocks:
        tk = sd['ticker']
        print(f"  [{tk}] PDF 생성 중...", end=' ', flush=True)
        try:
            path = generate_report(sd, tmp_dir)
            generated.append((tk, path))
            print("OK")
        except Exception as e:
            import traceback
            print(f"오류: {e}")
            traceback.print_exc()

    if not generated:
        print("[ERROR] 생성된 PDF 없음.")
        sys.exit(1)

    # 요약 페이지
    pdf_paths = [p for _, p in generated]
    summary_path = os.path.join(tmp_dir, f'_summary_{today_str}.pdf')
    print(f"\n  [SUMMARY] 생성 중...", end=' ', flush=True)
    try:
        generate_summary_page(stocks, summary_path)
        pdf_paths = [summary_path] + pdf_paths
        print("OK")
    except Exception as e:
        print(f"오류 (생략): {e}")

    # 병합
    suffix = '_' + ticker_list[0] if len(ticker_list) == 1 else ''
    merged = os.path.join(REPORTS_DIR, f'Quick_{today_str}{suffix}.pdf')
    merge_pdfs(pdf_paths, merged)

    size_kb = os.path.getsize(merged) // 1024
    print(f"\n  [완료] {merged}")
    print(f"         {len(generated)}개 종목 / {size_kb} KB")

    if auto_open:
        print(f"  [열기] PDF 오픈...")
        open_pdf(merged)

    return merged


if __name__ == '__main__':
    args = sys.argv[1:]

    auto_open = '--open' in args
    args = [a for a in args if a != '--open']

    tickers = [a.upper() for a in args] if args else None

    run(tickers=tickers, auto_open=auto_open)
