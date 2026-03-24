#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=======================================================
  Mag7 Stock Report → Email 전송 스크립트 (Gmail SMTP)
=======================================================

사전 준비:
  1. Gmail 2단계 인증 활성화
     https://myaccount.google.com/security
  2. 앱 비밀번호 발급
     Google 계정 → 보안 → 앱 비밀번호 → 앱: 메일, 기기: Windows
  3. GitHub Secrets 등록
     GMAIL_USER  : your@gmail.com
     GMAIL_APP_PW: xxxx xxxx xxxx xxxx  (앱 비밀번호 16자리)
     MAIL_TO     : recipient@email.com  (콤마로 여러 명 가능)

로컬 실행:
  python email_sender.py              # 오늘 리포트 전송
  python email_sender.py --test       # 테스트 메일 전송 (PDF 없이)
  python email_sender.py --latest     # 가장 최근 리포트 전송
"""

import os, sys, glob, datetime, smtplib, time
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders

# ══════════════════════════════════════════════════════════════════
#  설정 — GitHub Secrets 또는 로컬 환경변수로 주입
# ══════════════════════════════════════════════════════════════════

GMAIL_USER  = os.environ.get('GMAIL_USER',  '')   # 발신 Gmail 주소
GMAIL_APP_PW = os.environ.get('GMAIL_APP_PW', '')  # Gmail 앱 비밀번호
MAIL_TO     = os.environ.get('MAIL_TO',     '')   # 수신자 (콤마 구분 여러 명)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'cowork_agents', 'reports')

# ══════════════════════════════════════════════════════════════════


def _check_config():
    missing = [k for k, v in [('GMAIL_USER', GMAIL_USER),
                               ('GMAIL_APP_PW', GMAIL_APP_PW),
                               ('MAIL_TO', MAIL_TO)] if not v]
    if missing:
        print(f'[ERROR] 환경변수 미설정: {", ".join(missing)}')
        print('        .env 파일 또는 GitHub Secrets에 등록하세요.')
        return False
    return True


def get_today_pdf():
    today = datetime.date.today().strftime('%Y%m%d')
    path  = os.path.join(REPORTS_DIR, f'Mag7_Daily_Report_{today}.pdf')
    return path if os.path.exists(path) else None


def get_latest_pdf():
    pattern = os.path.join(REPORTS_DIR, 'Mag7_Daily_Report_*.pdf')
    pdfs    = sorted(glob.glob(pattern), reverse=True)
    return pdfs[0] if pdfs else None


def build_html_body(today_str, pdf_name):
    return f"""
<html><body style="font-family: 'Segoe UI', Arial, sans-serif; background:#f4f6f8; margin:0; padding:20px;">
<div style="max-width:600px; margin:0 auto; background:#ffffff; border-radius:12px;
            box-shadow:0 2px 12px rgba(0,0,0,0.08); overflow:hidden;">

  <!-- 헤더 -->
  <div style="background:#0C1E35; padding:28px 32px;">
    <h1 style="margin:0; color:#ffffff; font-size:22px; font-weight:700;">
      📊 Daily Stock Report
    </h1>
    <p style="margin:6px 0 0; color:#7FA8C8; font-size:13px;">
      {today_str} &nbsp;|&nbsp; 기술적 분석 종합
    </p>
  </div>

  <!-- 본문 -->
  <div style="padding:28px 32px;">
    <p style="color:#2C3E50; font-size:15px; line-height:1.7; margin:0 0 16px;">
      안녕하세요,<br>
      오늘의 주식 기술적 분석 리포트가 생성되었습니다.<br>
      첨부 PDF를 확인해 주세요.
    </p>

    <div style="background:#EAF2F8; border-left:4px solid #1A4A8A;
                padding:14px 18px; border-radius:6px; margin:20px 0;">
      <p style="margin:0; color:#1A4A8A; font-size:13px; font-weight:600;">
        📁 &nbsp;첨부 파일
      </p>
      <p style="margin:6px 0 0; color:#2C3E50; font-size:13px;">
        {pdf_name}
      </p>
    </div>

    <table style="width:100%; border-collapse:collapse; margin:20px 0;
                  font-size:13px; color:#2C3E50;">
      <tr style="background:#F8F9FA;">
        <td style="padding:10px 14px; border:1px solid #E0E0E0; font-weight:600;">타이밍 단계</td>
        <td style="padding:10px 14px; border:1px solid #E0E0E0; color:#1A8C5A; font-weight:600;">매수 적기 ≥63</td>
        <td style="padding:10px 14px; border:1px solid #E0E0E0; color:#1A4A8A;">매수 검토 50~62</td>
        <td style="padding:10px 14px; border:1px solid #E0E0E0; color:#CC7A2A;">관망 37~49</td>
        <td style="padding:10px 14px; border:1px solid #E0E0E0; color:#C0392B;">매도 주의 &lt;37</td>
      </tr>
    </table>

    <p style="color:#7F8C8D; font-size:12px; margin:24px 0 0;">
      본 리포트는 AI 기반 자동 기술적 분석으로, 투자 권유가 아닙니다.<br>
      Data: Yahoo Finance (yfinance) &nbsp;|&nbsp; AI Chart Analyst © 2026
    </p>
  </div>

  <!-- 푸터 -->
  <div style="background:#F4F6F8; padding:16px 32px; text-align:center;">
    <p style="margin:0; color:#95A5A6; font-size:11px;">
      Stock Report Manager &nbsp;·&nbsp; 매일 평일 오전 9시 KST 자동 발송
    </p>
  </div>

</div>
</body></html>
"""


def send_email(pdf_path=None):
    if not _check_config():
        return False

    today_str = datetime.date.today().strftime('%Y년 %m월 %d일')
    subject   = f'[Stock Report] {today_str} 기술적 분석 리포트'
    recipients = [r.strip() for r in MAIL_TO.split(',') if r.strip()]

    msg = MIMEMultipart('alternative')
    msg['From']    = GMAIL_USER
    msg['To']      = ', '.join(recipients)
    msg['Subject'] = subject

    # HTML 본문
    pdf_name = os.path.basename(pdf_path) if pdf_path else '리포트 없음'
    msg.attach(MIMEText(build_html_body(today_str, pdf_name), 'html', 'utf-8'))

    # PDF 첨부
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment',
                        filename=os.path.basename(pdf_path))
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PW)
            smtp.sendmail(GMAIL_USER, recipients, msg.as_string())
        print(f'  [EMAIL] 전송 완료 → {", ".join(recipients)}')
        return True
    except smtplib.SMTPAuthenticationError:
        print('[EMAIL ERROR] 인증 실패 — Gmail 앱 비밀번호를 확인하세요.')
        return False
    except Exception as e:
        print(f'[EMAIL ERROR] {e}')
        return False


def send_test():
    if not _check_config():
        return
    print('  [EMAIL] 테스트 메일 전송 중...')
    ok = send_email(pdf_path=None)
    print(f'  [EMAIL] {"테스트 성공" if ok else "테스트 실패"}')


# ── main ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    args = sys.argv[1:]

    if '--test' in args:
        send_test()
    elif '--latest' in args:
        pdf = get_latest_pdf()
        if pdf:
            send_email(pdf)
        else:
            print('[WARN] 전송할 PDF가 없습니다.')
    else:
        pdf = get_today_pdf()
        if not pdf:
            print('[INFO] 오늘 PDF 없음. 30초 후 재시도...')
            time.sleep(30)
            pdf = get_today_pdf()
        send_email(pdf)
