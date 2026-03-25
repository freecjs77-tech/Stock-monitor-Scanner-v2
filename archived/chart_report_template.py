#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
기술적 차트분석 리포트 PDF 생성 템플릿
사용법: 종목 데이터(DATA dict)를 채운 후 실행하면 됩니다.

한글 폰트: HYGothic-Medium (ReportLab 내장 CID — 외부 파일 불필요)
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import os, datetime

# ── 한글 CID 폰트 (항상 사용 가능, 외부 설치 불필요) ────────
pdfmetrics.registerFont(UnicodeCIDFont('HYGothic-Medium'))
F = 'HYGothic-Medium'

# ── 색상 ────────────────────────────────────────────────────
C_BUY       = colors.HexColor("#1A7A3C")   # 매수 녹색
C_SELL      = colors.HexColor("#C0392B")   # 매도 빨강
C_NEUTRAL   = colors.HexColor("#D35400")   # 중립 주황
C_NAVY      = colors.HexColor("#0D2137")   # 헤더 네이비
C_BLUE      = colors.HexColor("#1A56A8")   # 섹션 블루
C_LGRAY     = colors.HexColor("#F8F9FA")   # 배경 회색
C_BUY_BG    = colors.HexColor("#D4EDDA")   # 매수 배경
C_SELL_BG   = colors.HexColor("#FDECEA")   # 매도 배경
C_NEUT_BG   = colors.HexColor("#FFF3CD")   # 중립 배경
C_GRAY      = colors.HexColor("#6C757D")   # 회색 텍스트
C_BAR_EMPTY = colors.HexColor("#D0D0D0")   # 빈 바

# ── 스타일 ───────────────────────────────────────────────────
def ps(name, sz=9, color=colors.black, align=TA_LEFT, leading=None, sb=0, sa=2):
    return ParagraphStyle(name, fontName=F, fontSize=sz, textColor=color,
                          alignment=align, leading=leading or sz*1.5,
                          spaceBefore=sb, spaceAfter=sa)

S = {
    'h1':   ps('h1',  20, C_NAVY,  TA_CENTER, sa=3),
    'h2':   ps('h2',  12, C_BLUE,  TA_CENTER, sa=2),
    'date': ps('dt',   9, C_GRAY,  TA_CENTER, sa=2),
    'sec':  ps('sc',  11, C_NAVY,  sb=5, sa=2),
    'body': ps('bd',   9, colors.black, leading=15, sa=2),
    'em':   ps('em',   9, C_NAVY,  leading=15, sa=2),
    'th':   ps('th',   9, colors.white, TA_CENTER),
    'td':   ps('td',  8.5,colors.black, TA_LEFT),
    'tdc':  ps('tc',  8.5,colors.black, TA_CENTER),
    'sm':   ps('sm',  7.5,C_GRAY,  leading=11),
    'disc': ps('dc',  7.5,C_GRAY,  TA_CENTER, leading=11),
    'big_buy':  ps('bb', 15, C_BUY,  TA_CENTER),
    'big_sell': ps('bs', 15, C_SELL, TA_CENTER),
    'big_neut': ps('bn', 15, C_NEUTRAL, TA_CENTER),
    'score_lbl': ps('sl', 10, C_NAVY, TA_CENTER),
}

PAGE_W, PAGE_H = A4
MARGIN = 18*mm
COL_W  = PAGE_W - 2*MARGIN


def opinion_style(opinion_text):
    """투자의견에 따른 스타일 반환"""
    if '강한 매수' in opinion_text or '매수' in opinion_text:
        return S['big_buy']
    elif '강한 매도' in opinion_text or '매도' in opinion_text:
        return S['big_sell']
    return S['big_neut']

def opinion_bg(opinion_text):
    if '매수' in opinion_text:
        return C_BUY_BG
    elif '매도' in opinion_text:
        return C_SELL_BG
    return C_NEUT_BG


def score_bar_table(score, max_score, bar_color):
    """점수를 컬러 블록 바로 시각화"""
    cells = [Paragraph(" ", ps('bar', 4)) for _ in range(max_score)]
    t = Table([cells], colWidths=[4*mm]*max_score, rowHeights=[5*mm])
    style = [
        ('GRID',         (0,0),(-1,-1), 0.3, colors.white),
        ('BACKGROUND',   (0,0),(-1,0),  C_BAR_EMPTY),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
    ]
    if score > 0:
        style.append(('BACKGROUND', (0,0),(score-1,0), bar_color))
    t.setStyle(TableStyle(style))
    return t


def signal_row_color(signal_type):
    """매수/매도/중립에 따른 행 배경색"""
    if signal_type == 'buy':
        return C_BUY_BG
    elif signal_type == 'sell':
        return C_SELL_BG
    return C_NEUT_BG


def build_signal_table(signals, col_widths):
    """
    signals: [{'type': 'buy'|'sell'|'neutral', 'label': str, 'desc': str}, ...]
    col_widths: [w1, w2, ...]
    """
    hdr = [Paragraph('구분', S['th']),
           Paragraph('신호', S['th']),
           Paragraph('근거', S['th'])]
    rows = [hdr]
    style_cmds = [
        ('BACKGROUND', (0,0),(-1,0), C_NAVY),
        ('FONTNAME',   (0,0),(-1,-1), F),
        ('FONTSIZE',   (0,0),(-1,-1), 8.5),
        ('ALIGN',      (0,0),(1,-1), 'CENTER'),
        ('ALIGN',      (2,0),(2,-1), 'LEFT'),
        ('GRID',       (0,0),(-1,-1), 0.4, colors.lightgrey),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING', (2,0),(2,-1), 4),
    ]
    for i, sig in enumerate(signals):
        r = i + 1
        icon = '매수' if sig['type']=='buy' else ('매도' if sig['type']=='sell' else '중립')
        rows.append([
            Paragraph(icon, S['tdc']),
            Paragraph(sig['label'], S['tdc']),
            Paragraph(sig['desc'],  S['td']),
        ])
        style_cmds.append(('BACKGROUND', (0,r),(-1,r), signal_row_color(sig['type'])))
        if sig['type'] == 'buy':
            style_cmds.append(('TEXTCOLOR', (0,r),(0,r), C_BUY))
        elif sig['type'] == 'sell':
            style_cmds.append(('TEXTCOLOR', (0,r),(0,r), C_SELL))

    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle(style_cmds))
    return t


# ══════════════════════════════════════════════════════════════
# 메인 리포트 생성 함수
# ══════════════════════════════════════════════════════════════

def generate_chart_report(data: dict, output_path: str):
    """
    data 구조 (모든 항목은 문자열 또는 리스트):
    {
      'company':    '삼성전자',
      'ticker':     '005930',
      'exchange':   'KOSPI',
      'sector':     'IT/반도체',
      'date':       '2026-03-21',

      'current_price': '72,400원',
      '52w_high':      '88,700원',
      '52w_low':       '49,900원',
      '52w_position':  '55%',       # (현재가-저점)/(고점-저점)
      'prev_change':   '+1.2%',

      # 이동평균
      'ma20':  '71,200원',
      'ma60':  '68,500원',
      'ma120': '65,800원',
      'ma200': '63,100원',
      'ma_array': '정배열',         # 정배열 / 역배열 / 혼조
      'ma20_gap': '+1.7%',          # 이격도
      'ma200_gap': '+14.7%',

      # 점수 (각 분야별 실제 취득 점수, 음수 없음)
      'score_trend':   14,   # /20
      'score_momentum':12,   # /20
      'score_volatility':10, # /15
      'score_volume':  11,   # /15
      'score_pattern':  9,   # /15
      'score_bonus':    2,   # /5
      'score_total':   58,   # /85

      'opinion':  '매수',   # 강한 매수 / 매수 / 중립 / 매도 / 강한 매도

      # RSI·MACD·Stochastic
      'rsi':  '52.3',
      'rsi_status': '중립',
      'macd': '+245',
      'macd_signal': '+180',
      'macd_status': '매수 (시그널 상향 돌파)',
      'stoch_k': '62',
      'stoch_d': '58',
      'stoch_status': '중립',
      'momentum_divergence': '데이터 미확인',

      # 볼린저밴드
      'bb_upper': '76,500원',
      'bb_mid':   '71,200원',
      'bb_lower': '65,900원',
      'bb_pct_b': '0.61',
      'bb_squeeze': '확장 중',
      'atr': '2,100원',

      # 거래량
      'volume_cur':   '14,520,000주',
      'volume_avg20': '11,300,000주',
      'volume_ratio': '128%',
      'obv_trend': '상승',

      # 지지/저항
      'support1':  '70,000원',  'support1_reason': '20일 이동평균선',
      'support2':  '66,000원',  'support2_reason': '60일 이동평균선',
      'resist1':   '75,000원',  'resist1_reason':  '전고점 저항',
      'resist2':   '80,000원',  'resist2_reason':  '52주 고점 구간',

      # 패턴
      'pattern': '상승 깃발형 (Bull Flag)',
      'pattern_desc': '2월 급등 후 수렴 조정 중 — 상단 돌파 시 추가 상승 기대',

      # 신호 목록 (각 분야별)
      'signals_trend':      [{'type':'buy','label':'정배열','desc':'20>60>120>200일선 정배열 유지 — 상승 추세 확인'},
                              {'type':'buy','label':'200일선 위','desc':'현재가 200일선 대비 +14.7% 위에 위치'}],
      'signals_momentum':   [{'type':'buy','label':'MACD 골든','desc':'MACD +245 > 시그널 +180, 상향 돌파 확인'},
                              {'type':'neutral','label':'RSI 중립','desc':'RSI 52.3 — 과매수/과매도 아님'}],
      'signals_volatility': [{'type':'buy','label':'밴드 중심 위','desc':'현재가(%B=0.61) 중심선 위에서 안정적 흐름'},
                              {'type':'neutral','label':'밴드 확장','desc':'밴드폭 확장 중 — 추세 강화 진행'}],
      'signals_volume':     [{'type':'buy','label':'거래량 증가','desc':'평균 대비 128% — 상승 동반 거래량 확인'},
                              {'type':'buy','label':'OBV 상승','desc':'OBV 상승 추세 — 매수 우위 유지'}],
      'signals_pattern':    [{'type':'buy','label':'Bull Flag','desc':'상승 깃발형 수렴 중 — 상단 돌파 시 추가 상승 기대'},
                              {'type':'buy','label':'지지선 유지','desc':'70,000원 지지선(20일선) 유효 확인'}],

      # 매매 전략
      'entry_cond':  '현재가 또는 72,000원 이상 안착 확인 후 진입',
      'target1':     '75,000원 (+3.6%)',
      'target2':     '80,000원 (+10.5%)',
      'stop_loss':   '69,500원 (-4.0%)',
      'rr_ratio':    '1 : 2.6',

      'summary': '정배열 추세 + MACD 골든크로스 + 거래량 증가 복합 매수 신호 — 단기 상승 모멘텀 유효',

      # 총 매수/매도 신호 수
      'buy_count':  7,
      'sell_count': 2,
    }
    """

    d = data  # 별칭
    today = d.get('date', datetime.date.today().strftime('%Y-%m-%d'))

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=16*mm, bottomMargin=14*mm,
        title=f"{d['company']} 기술적 차트분석",
        author="AI Chart Analyst"
    )
    story = []

    # ── 헤더 ──────────────────────────────────────────────
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(f"{d['company']} ({d['ticker']} · {d['exchange']})", S['h1']))
    story.append(Paragraph("기 술 적 차 트 분 석 리 포 트", S['h2']))
    story.append(Paragraph(
        f"분석일: {today}  |  AI Chart Analyst  |  {d.get('sector','')}",
        S['date']))
    story.append(Spacer(1, 2*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=C_NAVY))
    story.append(Spacer(1, 3*mm))

    # ── 핵심 요약 박스 ──
    op = d['opinion']
    op_bg = opinion_bg(op)
    box = [
        [Paragraph("기술적 의견", S['th']),
         Paragraph("종합 점수", S['th']),
         Paragraph("신호 집계", S['th'])],
        [Paragraph(op, opinion_style(op)),
         Paragraph(f"{d['score_total']} / 85", S['score_lbl']),
         Paragraph(f"매수 {d['buy_count']}개 / 매도 {d['sell_count']}개",
                   S['score_lbl'])],
        [Paragraph(f"현재가: {d['current_price']}", S['score_lbl']),
         Paragraph(f"1차 목표가: {d['target1']}", S['score_lbl']),
         Paragraph(f"손절 기준: {d['stop_loss']}", S['score_lbl'])],
    ]
    box_t = Table(box, colWidths=[COL_W/3]*3, rowHeights=[9*mm, 16*mm, 9*mm])
    box_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,0), C_NAVY),
        ('BACKGROUND', (0,1),(-1,1), op_bg),
        ('BACKGROUND', (0,2),(-1,2), C_LGRAY),
        ('ALIGN',      (0,0),(-1,-1),'CENTER'),
        ('VALIGN',     (0,0),(-1,-1),'MIDDLE'),
        ('GRID',       (0,0),(-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(box_t)
    story.append(Spacer(1, 3*mm))

    # ── 5지표 스코어 바 ──
    story.append(Paragraph("■ 지표별 점수", S['sec']))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BLUE))
    story.append(Spacer(1, 1*mm))

    BAR_COL = C_BUY if d['score_total'] >= 55 else (C_NEUTRAL if d['score_total'] >= 40 else C_SELL)
    bar_items = [
        ('A. 추세 분석',   d['score_trend'],       20),
        ('B. 모멘텀 지표', d['score_momentum'],     20),
        ('C. 변동성',      d['score_volatility'],   15),
        ('D. 거래량',      d['score_volume'],       15),
        ('E. 패턴/지지저항', d['score_pattern'],    15),
    ]
    for label, sc, mx in bar_items:
        bar_color = C_BUY if sc >= mx*0.65 else (C_NEUTRAL if sc >= mx*0.4 else C_SELL)
        bar = score_bar_table(sc, mx, bar_color)
        row_t = Table(
            [[Paragraph(label, ps('bl',8.5,C_NAVY)), bar,
              Paragraph(f"{sc}/{mx}", ps('sr',8.5,bar_color,TA_RIGHT))]],
            colWidths=[50*mm, mx*3.2*mm, 14*mm],
            rowHeights=[7*mm]
        )
        row_t.setStyle(TableStyle([
            ('ALIGN',  (0,0),(0,0), 'LEFT'),
            ('ALIGN',  (2,0),(2,0), 'RIGHT'),
            ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(row_t)
        story.append(Spacer(1, 1*mm))

    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(
        f"핵심 요약: {d['summary']}", S['em']))
    story.append(Spacer(1, 3*mm))

    # ── A. 추세 분석 ──
    story.append(Paragraph(f"■ A. 추세 분석 (이동평균선)   {d['score_trend']}/20점", S['sec']))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BLUE))
    story.append(Spacer(1, 1*mm))

    ma_data = [
        [Paragraph('구분', S['th']), Paragraph('값', S['th']),
         Paragraph('현재가 대비', S['th']), Paragraph('판단', S['th'])],
        ['현재가', d['current_price'], '—', '기준'],
        ['20일선 (단기)', d['ma20'],  '단기 추세', '위' if '+' in d.get('ma20_gap','') else '아래'],
        ['60일선 (중기)', d['ma60'],  '중기 추세', '위'],
        ['120일선 (장기)', d['ma120'], '장기 추세', '위'],
        ['200일선 (초장기)', d['ma200'], f"이격도 {d.get('ma200_gap','')}", '위'],
    ]
    ma_t = Table(ma_data, colWidths=[42*mm, 38*mm, 35*mm, 55*mm])
    ma_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,0), C_BLUE),
        ('FONTNAME',   (0,0),(-1,-1), F),
        ('FONTSIZE',   (0,0),(-1,-1), 8.5),
        ('ALIGN',      (1,0),(-1,-1), 'CENTER'),
        ('ALIGN',      (0,0),(0,-1), 'LEFT'),
        ('GRID',       (0,0),(-1,-1), 0.4, colors.lightgrey),
        ('ROWBACKGROUNDS', (0,1),(-1,-1), [colors.white, C_LGRAY]),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING', (0,0),(0,-1), 4),
    ]))
    story.append(ma_t)
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(
        f"이동평균 배열: {d['ma_array']}  |  20일 이격도: {d.get('ma20_gap','미확인')}  |  200일 이격도: {d.get('ma200_gap','미확인')}",
        S['body']))
    story.append(Spacer(1, 1*mm))
    story.append(build_signal_table(d['signals_trend'], [18*mm, 48*mm, 104*mm]))
    story.append(Spacer(1, 3*mm))

    # ── B. 모멘텀 지표 ──
    story.append(Paragraph(f"■ B. 모멘텀 지표 (RSI·MACD·스토캐스틱)   {d['score_momentum']}/20점", S['sec']))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BLUE))
    story.append(Spacer(1, 1*mm))

    mom_data = [
        [Paragraph('지표', S['th']), Paragraph('값', S['th']),
         Paragraph('상태', S['th'])],
        ['RSI (14일)',           d['rsi'],       d['rsi_status']],
        ['MACD',                d['macd'],      d['macd_status']],
        ['MACD 시그널선',        d['macd_signal'], '—'],
        ['스토캐스틱 %K',        d['stoch_k'],   d['stoch_status']],
        ['스토캐스틱 %D',        d['stoch_d'],   '—'],
        ['다이버전스',           '—',            d.get('momentum_divergence','데이터 미확인')],
    ]
    mom_t = Table(mom_data, colWidths=[45*mm, 45*mm, 80*mm])
    mom_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,0), C_BLUE),
        ('FONTNAME',   (0,0),(-1,-1), F),
        ('FONTSIZE',   (0,0),(-1,-1), 8.5),
        ('ALIGN',      (1,0),(-1,-1), 'CENTER'),
        ('ALIGN',      (0,0),(0,-1), 'LEFT'),
        ('GRID',       (0,0),(-1,-1), 0.4, colors.lightgrey),
        ('ROWBACKGROUNDS', (0,1),(-1,-1), [colors.white, C_LGRAY]),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING', (0,0),(0,-1), 4),
    ]))
    story.append(mom_t)
    story.append(Spacer(1, 1*mm))
    story.append(build_signal_table(d['signals_momentum'], [18*mm, 48*mm, 104*mm]))
    story.append(Spacer(1, 3*mm))

    # ── C. 변동성 ──
    story.append(Paragraph(f"■ C. 변동성 (볼린저밴드·ATR)   {d['score_volatility']}/15점", S['sec']))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BLUE))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(
        f"볼린저밴드: 상단 {d['bb_upper']}  |  중심선 {d['bb_mid']}  |  하단 {d['bb_lower']}  |  "
        f"%B = {d['bb_pct_b']}  |  밴드 상태: {d['bb_squeeze']}  |  ATR: {d['atr']}",
        S['body']))
    story.append(Spacer(1, 1*mm))
    story.append(build_signal_table(d['signals_volatility'], [18*mm, 48*mm, 104*mm]))
    story.append(Spacer(1, 3*mm))

    # ── D. 거래량 ──
    story.append(Paragraph(f"■ D. 거래량 분석   {d['score_volume']}/15점", S['sec']))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BLUE))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(
        f"현재 거래량: {d['volume_cur']}  |  20일 평균: {d['volume_avg20']}  |  "
        f"비율: {d['volume_ratio']}  |  OBV 추세: {d['obv_trend']}",
        S['body']))
    story.append(Spacer(1, 1*mm))
    story.append(build_signal_table(d['signals_volume'], [18*mm, 48*mm, 104*mm]))
    story.append(Spacer(1, 3*mm))

    # ── E. 차트 패턴 + 지지/저항 ──
    story.append(Paragraph(f"■ E. 차트 패턴 · 지지선/저항선   {d['score_pattern']}/15점", S['sec']))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BLUE))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(
        f"인식 패턴: {d['pattern']}  —  {d['pattern_desc']}", S['body']))
    story.append(Spacer(1, 1*mm))

    sr_data = [
        [Paragraph('구분', S['th']), Paragraph('가격', S['th']), Paragraph('근거', S['th'])],
        ['지지선 ①', d['support1'], d['support1_reason']],
        ['지지선 ②', d['support2'], d['support2_reason']],
        ['저항선 ①', d['resist1'],  d['resist1_reason']],
        ['저항선 ②', d['resist2'],  d['resist2_reason']],
    ]
    sr_t = Table(sr_data, colWidths=[28*mm, 42*mm, 100*mm])
    sr_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,0), C_BLUE),
        ('FONTNAME',   (0,0),(-1,-1), F),
        ('FONTSIZE',   (0,0),(-1,-1), 8.5),
        ('ALIGN',      (0,0),(1,-1), 'CENTER'),
        ('ALIGN',      (2,0),(2,-1), 'LEFT'),
        ('GRID',       (0,0),(-1,-1), 0.4, colors.lightgrey),
        ('BACKGROUND', (0,1),(-1,2), C_BUY_BG),
        ('BACKGROUND', (0,3),(-1,4), C_SELL_BG),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING', (2,0),(2,-1), 4),
    ]))
    story.append(sr_t)
    story.append(Spacer(1, 1*mm))
    story.append(build_signal_table(d['signals_pattern'], [18*mm, 48*mm, 104*mm]))

    # ── 페이지 2: 종합 + 매매전략 ──
    story.append(PageBreak())

    story.append(Paragraph("■ 종합 스코어카드", S['sec']))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BLUE))
    story.append(Spacer(1, 1*mm))

    sc_data = [
        [Paragraph('분석 항목', S['th']), Paragraph('취득', S['th']),
         Paragraph('배점', S['th']), Paragraph('핵심', S['th'])],
        ['A. 추세 (이동평균, 배열)',      str(d['score_trend']),      '/20', '정/역배열, 이격도, 골든/데드크로스'],
        ['B. 모멘텀 (RSI·MACD·Stoch)',   str(d['score_momentum']),   '/20', 'RSI 과매수/과매도, MACD 교차, 다이버전스'],
        ['C. 변동성 (볼린저밴드·ATR)',    str(d['score_volatility']), '/15', '%B 위치, Squeeze, 밴드 돌파 여부'],
        ['D. 거래량 (Volume·OBV)',       str(d['score_volume']),     '/15', '평균 대비 거래량, OBV 추세 방향'],
        ['E. 패턴·지지/저항',            str(d['score_pattern']),    '/15', '차트 패턴, 피보나치, 주요 가격대'],
        ['보너스 (복합 강신호)',          str(d['score_bonus']),      '/5',  '강신호 복합 확인'],
        [Paragraph('종 합', S['th']),
         Paragraph(str(d['score_total']), S['th']),
         Paragraph('/85', S['th']),
         Paragraph(d['opinion'], S['th'])],
    ]
    sc_t = Table(sc_data, colWidths=[55*mm, 18*mm, 18*mm, 79*mm])
    op_row_bg = C_BUY_BG if '매수' in op else (C_SELL_BG if '매도' in op else C_NEUT_BG)
    sc_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,0), C_NAVY),
        ('BACKGROUND', (0,-1),(-1,-1), op_row_bg),
        ('FONTNAME',   (0,0),(-1,-1), F),
        ('FONTSIZE',   (0,0),(-1,-1), 9),
        ('ALIGN',      (1,0),(2,-1), 'CENTER'),
        ('ALIGN',      (0,0),(0,-1), 'LEFT'),
        ('ALIGN',      (3,0),(3,-1), 'LEFT'),
        ('GRID',       (0,0),(-1,-1), 0.4, colors.lightgrey),
        ('ROWBACKGROUNDS', (0,1),(-1,-2), [colors.white, C_LGRAY]),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING', (0,0),(0,-1), 4),
        ('LEFTPADDING', (3,0),(3,-1), 4),
    ]))
    story.append(sc_t)
    story.append(Spacer(1, 5*mm))

    # ── 매매 전략 박스 ──
    story.append(Paragraph("■ 매매 전략", S['sec']))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BLUE))
    story.append(Spacer(1, 1*mm))

    strat_data = [
        [Paragraph('항목', S['th']), Paragraph('내용', S['th'])],
        ['진입 조건',        d['entry_cond']],
        ['1차 목표가',       d['target1']],
        ['2차 목표가',       d['target2']],
        ['손절 기준',        d['stop_loss']],
        ['리스크/리워드',    d['rr_ratio']],
    ]
    strat_t = Table(strat_data, colWidths=[38*mm, 132*mm])
    strat_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,0), C_NAVY),
        ('FONTNAME',   (0,0),(-1,-1), F),
        ('FONTSIZE',   (0,0),(-1,-1), 9),
        ('ALIGN',      (0,0),(0,-1), 'LEFT'),
        ('GRID',       (0,0),(-1,-1), 0.4, colors.lightgrey),
        ('ROWBACKGROUNDS', (0,1),(-1,2), [C_BUY_BG, C_BUY_BG]),
        ('BACKGROUND', (0,4),(-1,4), C_SELL_BG),
        ('ROWBACKGROUNDS', (0,1),(-1,-1), [colors.white, C_LGRAY]),
        ('VALIGN',     (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING', (0,0),(-1,-1), 6),
    ]))
    story.append(strat_t)
    story.append(Spacer(1, 8*mm))

    # ── 면책 ──
    story.append(HRFlowable(width="100%", thickness=1, color=C_GRAY))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("[ 면책 조항 ]", ps('dh', 9, C_GRAY, TA_CENTER)))
    story.append(Paragraph(
        f"본 보고서는 AI 기반 자동 기술적 분석으로, 투자 권유가 아닙니다. "
        f"모든 데이터는 {today} 기준 웹 검색으로 확인된 실제 수치이나 "
        f"일부 항목은 검색 한계로 추정치가 포함될 수 있습니다. "
        f"투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.  |  AI Chart Analyst (c) 2026",
        S['disc']))

    doc.build(story)
    print(f"[OK] PDF 생성 완료: {output_path}")


# ══════════════════════════════════════════════════════════════
# 예시 데이터 (삼성전자 샘플 — 실제 분석 시 채워서 사용)
# ══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    import os

    SAMPLE_DATA = {
        'company': '삼성전자',
        'ticker':  '005930',
        'exchange': 'KOSPI',
        'sector':  'IT/반도체',
        'date':    '2026-03-21',

        'current_price': '205,000원',
        '52w_high':  '223,000원',
        '52w_low':   '52,900원',
        '52w_position': '90%',
        'prev_change': '+1.5%',

        'ma20':  '198,500원',
        'ma60':  '185,200원',
        'ma120': '168,400원',
        'ma200': '152,700원',
        'ma_array': '정배열',
        'ma20_gap':  '+3.3%',
        'ma200_gap': '+34.3%',

        'score_trend':      16,
        'score_momentum':   13,
        'score_volatility': 10,
        'score_volume':     11,
        'score_pattern':    10,
        'score_bonus':       2,
        'score_total':      62,
        'opinion':          '매수',
        'buy_count': 8,
        'sell_count': 2,

        'rsi':          '61.4',
        'rsi_status':   '중립~과매수 경계',
        'macd':         '+3,420',
        'macd_signal':  '+2,850',
        'macd_status':  '매수 (시그널 상향 유지)',
        'stoch_k':      '72',
        'stoch_d':      '65',
        'stoch_status': '과매수 진입 주의',
        'momentum_divergence': '데이터 미확인',

        'bb_upper': '215,000원',
        'bb_mid':   '198,500원',
        'bb_lower': '182,000원',
        'bb_pct_b': '0.70',
        'bb_squeeze': '확장 중',
        'atr':      '4,200원',

        'volume_cur':   '22,450,000주',
        'volume_avg20': '18,200,000주',
        'volume_ratio': '123%',
        'obv_trend': '상승',

        'support1': '198,500원', 'support1_reason': '20일 이동평균선 지지',
        'support2': '185,200원', 'support2_reason': '60일 이동평균선 지지',
        'resist1':  '215,000원', 'resist1_reason':  '볼린저밴드 상단',
        'resist2':  '223,000원', 'resist2_reason':  '52주 신고가',

        'pattern':      '상승 추세 지속 (Uptrend)',
        'pattern_desc': '정배열 유지 + MACD 골든크로스 + 거래량 증가 — 단기 추가 상승 모멘텀',

        'signals_trend': [
            {'type':'buy',  'label':'정배열',     'desc':'20>60>120>200일선 정배열 유지 — 강한 상승 추세 확인'},
            {'type':'buy',  'label':'200일선 위', 'desc':'현재가 200일선 대비 +34.3% 위 — 장기 강세'},
            {'type':'sell', 'label':'고점 인근',  'desc':'52주 고점(223,000원) 대비 -8% — 저항 구간'},
        ],
        'signals_momentum': [
            {'type':'buy',     'label':'MACD 매수', 'desc':'MACD +3,420 > 시그널 +2,850 — 상향 유지'},
            {'type':'neutral', 'label':'RSI 61.4',  'desc':'과매수 경계(70) 아래 — 추가 상승 여지'},
            {'type':'sell',    'label':'스토캐스틱', 'desc':'%K=72, %D=65 — 과매수(80) 임박 주의'},
        ],
        'signals_volatility': [
            {'type':'buy',     'label':'밴드 중심 위', 'desc':'%B=0.70, 중심선 위에서 안정적 흐름'},
            {'type':'neutral', 'label':'밴드 확장',    'desc':'밴드폭 확장 중 — 추세 강화 진행'},
        ],
        'signals_volume': [
            {'type':'buy', 'label':'거래량 증가', 'desc':'평균 대비 123% — 상승 동반 거래량 확인'},
            {'type':'buy', 'label':'OBV 상승',   'desc':'OBV 상승 추세 지속 — 매수 우위'},
        ],
        'signals_pattern': [
            {'type':'buy',  'label':'지지선 유지', 'desc':'198,500원(20일선) 지지 유효 확인'},
            {'type':'sell', 'label':'저항 인근',   'desc':'215,000원 볼린저 상단 저항 — 조정 가능성'},
        ],

        'entry_cond': '현재가(205,000원) 또는 198,500원 지지 확인 후 재진입',
        'target1':    '215,000원 (+4.9%)',
        'target2':    '223,000원 (+8.8%)',
        'stop_loss':  '194,000원 (-5.4%)',
        'rr_ratio':   '1 : 1.6',
        'summary':    '정배열 + MACD 골든크로스 + 거래량 증가 — 단기 매수 모멘텀 유효, 223,000원 저항 돌파 여부 주목',
    }

    out_dir = "/sessions/keen-eloquent-thompson/mnt/Stock-Analyst/cowork_agents/reports"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "삼성전자_005930_차트분석_20260321.pdf")
    generate_chart_report(SAMPLE_DATA, out_path)
