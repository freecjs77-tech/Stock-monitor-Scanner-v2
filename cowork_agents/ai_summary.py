"""
ai_summary.py — Groq API를 사용한 시장 요약 + 판정 조건 설명 생성
- generate_ai_summary(): 전체 종목 시장 요약 (1회 호출)
- generate_condition_explanation(): 종목별 판정 근거 친근한 설명 (종목당 1회)
- 실패 시 None 반환 (fallback: 빈 문자열)
"""

import os
import json
import re
import datetime


def generate_ai_summary(stocks_list):
    """
    Groq API로 시장 요약 생성.

    Returns:
        dict 또는 None (API 실패 시)
        {
            "weather_title": "오늘의 시장 날씨: 조금은 흐림, 하지만 기회는 솔솔",
            "market_overview": "오늘 시장은 전반적으로 힘이 조금 빠진 모습이에요...",
            "stocks": {
                "NVDA": {"summary": "...", "key_point": "..."},
                ...
            },
            "investment_points": [
                "현금 비중은 든든하게: ...",
                "금/은에 주목: ...",
                "지표의 신호: ..."
            ]
        }
    """
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        print("  [AI] GROQ_API_KEY 없음 — 규칙 기반 텍스트 사용")
        return None

    try:
        from groq import Groq
    except ImportError:
        print("  [AI] groq 패키지 미설치 — pip install groq")
        return None

    today_str = datetime.date.today().strftime('%Y년 %m월 %d일')

    # 프롬프트용 종목 데이터 압축
    stock_summaries = []
    for d in stocks_list:
        ticker  = d['ticker']
        company = d.get('company', ticker)
        c       = d['close']
        chg     = d.get('chg_pct', 0)
        m20     = d['ma20']
        m50     = d.get('ma50', 0)
        m200    = d.get('ma200', 0)
        rsi     = d['rsi']
        macd    = d['macd']
        macd_s  = d.get('macd_signal', 0)
        h52     = d.get('high_52w', c * 1.3)
        drop    = round((1 - c / h52) * 100, 1)
        above   = sum([c > m20, c > m50, c > m200])
        macd_dir = "상승" if macd > macd_s else "하락"
        chg_sign = "+" if chg >= 0 else ""

        stock_summaries.append(
            f"{ticker}({company}): 현재가=${c:.2f}({chg_sign}{chg:.2f}%), RSI={rsi:.1f}, "
            f"MACD {macd_dir}, MA20={'위' if c > m20 else '아래'}, "
            f"이평선 {above}/3개 위, 52주고점대비 -{drop}%"
        )

    tickers_str = ', '.join(d['ticker'] for d in stocks_list)

    prompt = f"""당신은 친근한 주식 투자 전문가입니다. {today_str} 기준 기술적 지표를 바탕으로 비전문가도 쉽게 이해할 수 있는 시장 요약을 작성해주세요.

종목 데이터:
{chr(10).join(stock_summaries)}

다음 JSON 형식으로만 답하세요. JSON 외 다른 텍스트는 절대 포함하지 마세요:
{{
  "weather_title": "오늘의 시장 날씨를 날씨에 비유한 한 줄 제목 (예: '조금은 흐림, 하지만 기회는 솔솔')",
  "market_overview": "전체 시장 분위기를 2문장으로 친근하게 설명. 종목별 점수가 전반적으로 낮거나 높은지 언급",
  "stocks": {{
    "NVDA": {{
      "summary": "이 종목 상황을 1~2문장, 친근한 말투로 (현재가/등락률/핵심 이유 포함, 80자 이내)",
      "key_point": "지금 가장 주목할 포인트 한 줄 (예: 'MA20 $181 돌파 여부가 핵심')"
    }}
  }},
  "investment_points": [
    "투자 포인트 1: 제목: 설명 (현재 시장 전체에 해당하는 행동 조언)",
    "투자 포인트 2: 제목: 설명",
    "투자 포인트 3: 제목: 설명"
  ]
}}

종목 목록 (반드시 모두 포함): {tickers_str}

말투 규칙:
- 존댓말, 친근하게 (~예요, ~해요, ~거예요)
- 숫자/수치는 꼭 필요한 것만 사용
- weather_title은 날씨/감성 표현으로 (예: '구름 사이로 햇살이', '잔뜩 흐린 하늘')
- investment_points는 '제목: 설명' 형식으로 실용적 조언"""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()

        # JSON 파싱 (마크다운 코드블록 제거)
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        result = json.loads(raw)

        # 필수 키 보정
        result.setdefault('weather_title', '오늘의 시장 분위기')
        result.setdefault('market_overview', '')
        result.setdefault('investment_points', [])
        if 'stocks' not in result:
            result['stocks'] = {}
        for d in stocks_list:
            t = d['ticker']
            if t not in result['stocks']:
                result['stocks'][t] = {"summary": "", "key_point": ""}

        print(f"  [AI] Groq 요약 완료 ({len(stocks_list)}개 종목)")
        return result

    except json.JSONDecodeError as e:
        print(f"  [AI] JSON 파싱 실패: {e} — 규칙 기반 사용")
        return None
    except Exception as e:
        print(f"  [AI] API 오류: {e} — 규칙 기반 사용")
        return None


def generate_condition_explanation(d):
    """
    Groq API로 종목 판정 근거를 친근한 한국어로 설명.

    Returns:
        str: 2~3문장 설명 텍스트, 실패 시 빈 문자열 ''
    """
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return ''

    try:
        from groq import Groq
    except ImportError:
        return ''

    ticker  = d.get('ticker', '')
    rsi     = d.get('rsi', 0)
    adx     = d.get('adx', 0)
    chg     = d.get('change_pct', 0)
    close   = d.get('close', 0)
    ma20    = d.get('ma20', close)
    ma50    = d.get('ma50', close)
    ma200   = d.get('ma200', close)

    def sig(key):
        return bool(d.get(key, False))

    # 현재 판정 계산
    from report_engine import trading_signal
    sk, lbl, _ = trading_signal(d)

    # 조건 충족 현황 텍스트
    if sk == '1st_BUY':
        conds = []
        if sig('sig_rsi_le38'):    conds.append(f'RSI {rsi:.1f} (≤38 충족)')
        else:                      conds.append(f'RSI {rsi:.1f} (≤38 미충족)')
        if sig('sig_adx_le25'):    conds.append(f'ADX {adx:.1f} (≤25 충족)')
        else:                      conds.append(f'ADX {adx:.1f} (≤25 미충족)')
        if sig('sig_below_ma20'):  conds.append('종가<MA20 충족')
        else:                      conds.append('종가<MA20 미충족')
        if sig('sig_low_stopped'): conds.append('하락멈춤 충족')
        else:                      conds.append('하락멈춤 미충족')
        if sig('sig_near_bb_low'): conds.append('BB하단 충족')
        else:                      conds.append('BB하단 미충족')
        if sig('sig_bounce2pct'):  conds.append(f'당일+2% 충족({chg:+.1f}%)')
        else:                      conds.append(f'당일+2% 미충족({chg:+.1f}%)')
        met = sum([sig('sig_rsi_le38'), sig('sig_adx_le25'), sig('sig_below_ma20'),
                   sig('sig_low_stopped'), sig('sig_near_bb_low'), sig('sig_bounce2pct')])
        cond_text = f'1차 매수 조건 {met}/6개 충족\n' + ', '.join(conds)

    elif sk == '2nd_BUY':
        conds = []
        if sig('sig_double_bottom'):                          conds.append('이중바닥 충족')
        else:                                                 conds.append('이중바닥 미충족')
        if sig('sig_rsi_gt35') and sig('sig_rsi_3d_up'):     conds.append(f'RSI {rsi:.1f} 3일↑ 충족')
        else:                                                 conds.append(f'RSI {rsi:.1f} 반등 미확인')
        if sig('sig_macd_golden') or sig('sig_macd_hist_3d_up'): conds.append('MACD 전환 충족')
        else:                                                 conds.append('MACD 전환 미충족')
        if sig('sig_vol_1p2'):                                conds.append('거래량 1.2배 충족')
        else:                                                 conds.append('거래량 부족')
        cond_text = '2차 매수 조건 4/4개 충족\n' + ', '.join(conds)

    elif sk == '3rd_BUY':
        conds = []
        if sig('sig_above_ma20_2d'):    conds.append('MA20 안착 충족')
        else:                           conds.append('MA20 안착 미충족')
        if sig('sig_ma20_slope_pos'):   conds.append('MA20 기울기↑ 충족')
        else:                           conds.append('MA20 기울기 하향')
        if sig('sig_macd_above_zero'):  conds.append('MACD 0선↑ 충족')
        else:                           conds.append('MACD 음수')
        if sig('sig_vol_1p3'):          conds.append('거래량 1.3배 충족')
        else:                           conds.append('거래량 부족')
        cond_text = '3차 매수 조건 4/4개 충족\n' + ', '.join(conds)

    else:  # watch
        met = sum([sig('sig_rsi_le38'), sig('sig_adx_le25'), sig('sig_below_ma20'),
                   sig('sig_low_stopped'), sig('sig_near_bb_low'), sig('sig_bounce2pct')])
        block_reason = ''
        if sig('sig_block_rsi50'):    block_reason = f' (RSI {rsi:.1f} > 50 — 매수 차단)'
        elif sig('sig_block_bigdrop'): block_reason = f' (장대음봉 {chg:.1f}% — 매수 차단)'
        cond_text = f'1차 매수 조건 {met}/6개만 충족{block_reason} — 조건 미달로 관망'

    prompt = f"""{ticker} 종목의 기술적 분석 판정 결과를 친근하게 설명해주세요.

현재가: ${close:.2f} | RSI: {rsi:.1f} | ADX: {adx:.1f} | 당일: {chg:+.1f}%
MA 상태: MA20=${ma20:.2f}, MA50=${ma50:.2f}, MA200=${ma200:.2f}
판정 결과: {lbl}
{cond_text}

규칙:
- 2~3문장으로 짧고 친근하게 (반말 금지, ~예요/~해요 말투)
- "왜 이 판정이 나왔는지"를 중심으로
- 숫자는 꼭 필요한 것만, 어려운 용어는 괄호로 풀어서
- 마지막 문장은 "지금 어떻게 볼지" 한 줄로 마무리
- JSON 없이 순수 텍스트만 출력"""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        print(f"  [AI-조건] {ticker} 설명 완료")
        return text
    except Exception as e:
        print(f"  [AI-조건] {ticker} 오류: {e}")
        return ''
