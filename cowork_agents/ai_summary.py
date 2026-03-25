"""
ai_summary.py — Groq API를 사용한 시장 요약 생성
- 7종목 데이터를 한 번의 API 호출로 요약
- 실패 시 None 반환 (fallback: 기존 규칙 기반 텍스트 사용)
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
