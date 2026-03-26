#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=======================================================
  Mag7 Stock Report → Telegram 전송 스크립트
  로컬 Windows PC에서 실행 (Task Scheduler 등록용)
=======================================================

필요 라이브러리 설치:
  pip install requests

실행 방법:
  python telegram_sender.py              # 오늘 날짜 리포트 전송
  python telegram_sender.py --test       # 테스트 메시지만 전송 (PDF 없이)
  python telegram_sender.py --all        # 폴더의 모든 PDF 전송
  python telegram_sender.py --setup      # Chat ID 자동 감지
"""

import os, sys, glob, datetime, time
import requests

# ══════════════════════════════════════════════════════════════════
#  설정 (여기만 수정하세요)
# ══════════════════════════════════════════════════════════════════

# GitHub Actions에서는 환경변수(Secrets)로 주입, 로컬에서는 아래 값 사용
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID   = os.environ.get("CHAT_ID",   "")

# 리포트 폴더 경로 (Windows 경로로 수정 필요)
# 예: r"C:\Users\YourName\OneDrive\Documents\Claude\Stock-Analyst\cowork_agents\reports"
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "cowork_agents", "reports")

# ══════════════════════════════════════════════════════════════════

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_chat_id():
    """봇에 메시지를 보낸 사용자의 Chat ID를 자동 감지"""
    print("\n[SETUP] @MyStockMonitor_bot 에 /start 를 보낸 후 Enter 를 누르세요...")
    input()
    r = requests.get(f"{API_BASE}/getUpdates", timeout=10)
    data = r.json()
    if data.get('ok') and data.get('result'):
        for msg in reversed(data['result']):
            chat = msg.get('message', {}).get('chat', {})
            if chat:
                cid = chat['id']
                name = chat.get('first_name', '') + ' ' + chat.get('last_name', '')
                print(f"\n[SETUP] Chat ID 감지됨: {cid}  (이름: {name.strip()})")
                print(f"[SETUP] telegram_sender.py 파일의 CHAT_ID = \"{cid}\" 로 설정하세요.")
                return str(cid)
    print("[SETUP] Chat ID를 찾을 수 없습니다. 봇에 메시지를 보낸 후 다시 시도하세요.")
    return None


def send_message(text):
    """텍스트 메시지 전송"""
    r = requests.post(f"{API_BASE}/sendMessage",
                      data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'},
                      timeout=15)
    return r.json().get('ok', False)


def send_pdf(pdf_path, caption=""):
    """PDF 파일 전송"""
    with open(pdf_path, 'rb') as f:
        r = requests.post(f"{API_BASE}/sendDocument",
                          data={'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'},
                          files={'document': (os.path.basename(pdf_path), f, 'application/pdf')},
                          timeout=60)
    result = r.json()
    return result.get('ok', False), result.get('description', '')


def send_url(report_url, summary_lines=None):
    """HTML 리포트 URL을 텔레그램으로 전송"""
    if not BOT_TOKEN or not CHAT_ID:
        print("[ERROR] BOT_TOKEN 또는 CHAT_ID 미설정")
        return False

    today_str = datetime.date.today().strftime('%Y년 %m월 %d일')

    text = f"📊 <b>관심 종목 일일 리포트</b>  —  {today_str}\n\n"
    if summary_lines:
        for line in summary_lines:
            text += f"{line}\n"
        text += "\n"
    text += f"👉 <a href='{report_url}'>전체 리포트 보기</a>"

    r = requests.post(f"{API_BASE}/sendMessage",
                      data={'chat_id': CHAT_ID, 'text': text,
                            'parse_mode': 'HTML', 'disable_web_page_preview': False},
                      timeout=30)
    ok = r.status_code == 200
    print(f"  [TG] URL 발송 {'성공' if ok else '실패'}: {report_url}")
    return ok


def get_today_pdf():
    """오늘 날짜의 통합 PDF 반환"""
    today = datetime.date.today().strftime('%Y%m%d')
    path = os.path.join(REPORTS_DIR, f'Mag7_Daily_Report_{today}.pdf')
    return path if os.path.exists(path) else None


def get_latest_pdf():
    """가장 최근 통합 PDF 반환"""
    pattern = os.path.join(REPORTS_DIR, 'Mag7_Daily_Report_*.pdf')
    pdfs = sorted(glob.glob(pattern), reverse=True)
    return pdfs[0] if pdfs else None


def run_send(pdf_path=None, label="오늘"):
    if not CHAT_ID:
        print("[ERROR] CHAT_ID가 설정되지 않았습니다.")
        print("        먼저 python telegram_sender.py --setup 을 실행하세요.")
        sys.exit(1)

    if not pdf_path:
        send_message(f"⚠️ {label} 생성된 리포트가 없습니다.\n리포트 폴더: {REPORTS_DIR}")
        print(f"[WARN] {label} PDF 없음")
        return

    today_str = datetime.date.today().strftime('%Y년 %m월 %d일')
    caption = (f"📊 <b>관심 종목 기술적 분석 리포트</b>\n"
               f"📅 {today_str}  |  NVDA / PLTR / TSLA / AAPL / MSFT / GOOGL / AMZN / META\n"
               f"⏰ {datetime.datetime.now().strftime('%H:%M')}")

    print(f"  [SEND] {os.path.basename(pdf_path)} ...")
    ok, err = send_pdf(pdf_path, caption)
    if ok:
        print(f"  [OK] 전송 완료")
    else:
        print(f"  [FAIL] {err}")
        return

    print(f"\n[DONE] 전송 완료")


def run_test():
    if not CHAT_ID:
        print("[ERROR] CHAT_ID 미설정. --setup 먼저 실행하세요.")
        sys.exit(1)
    msg = ("🤖 <b>MStockMonitor Bot 연결 테스트</b>\n\n"
           "✅ 봇이 정상적으로 연결되었습니다!\n"
           "매일 평일 오전 9:30에 관심 종목 리포트가 자동 전송됩니다.\n\n"
           f"📁 리포트 폴더:\n<code>{REPORTS_DIR}</code>")
    ok = send_message(msg)
    print(f"[TEST] {'성공' if ok else '실패'}")


# ── main ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    args = sys.argv[1:]

    if '--setup' in args:
        get_chat_id()
    elif '--test' in args:
        run_test()
    elif '--latest' in args:
        pdf = get_latest_pdf()
        run_send(pdf, "최신")
    else:
        # 기본: 오늘 날짜 통합 리포트 전송
        pdf = get_today_pdf()
        # 오늘 파일 없으면 30초 대기 후 재시도 (리포트 생성 타이밍 여유)
        if not pdf:
            print("[INFO] 오늘 PDF 없음. 30초 후 재시도...")
            time.sleep(30)
            pdf = get_today_pdf()
        run_send(pdf, "오늘")
