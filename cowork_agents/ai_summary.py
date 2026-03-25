"""
ai_summary.py — Groq API를 사용한 시장 요약 생성
- 7종목 데이터를 한 번의 API 호출로 요약
- 실패 시 None 반환 (fallback: 기존 규칙 기반 텍스트 사용)
"""

import os
import json
import re


def generate_ai_summary(stocks_list):
    """
    Groq API로 시장 요약 생성.

    Returns:
        dict 또는 None (API 실패 시)
        {
            "market_overview": "오늘 시장은 전반적으로...",
            "stocks": {
                "NVDA": {"summary": "...", "key_point": "..."},
                ...
            }
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

    # 프롬프트용 종목 데이터 압축
    stock_summaries = []
    for d in stocks_list:
        ticker = d['ticker']
        c      = d['close']
        m20    = d['ma20']
        m50    = d.get('ma50', 0)
        m200   = d.get('ma200', 0)
        rsi    = d['rsi']
        macd   = d['macd']
        macd_s = d.get('macd_signal', 0)
        h52    = d.get('high_52w', c * 1.3)
        l52    = d.get('low_52w',  c * 0.7)
        drop   = round((1 - c / h52) * 100, 1)
        above  = sum([c > m20, c > m50, c > m200])
        macd_dir = "상승" if macd > macd_s else "하락"

        stock_summaries.append(
            f"{ticker}: 현재가=${c:.2f}, RSI={rsi:.1f}, MACD {macd_dir}, "
            f"MA20=${m20:.2f}({'위' if c > m20 else '아래'}), "
            f"이평선 {above}/3개 위, 52주고점대비 -{drop}%"
        )

    prompt = f"""당신은 주식 투자 전문가입니다. 아래 기술적 지표를 바탕으로 친근하고 쉬운 한국어로 요약해주세요.

종목 데이터:
{chr(10).join(stock_summaries)}

다음 JSON 형식으로만 답하세요. JSON 외 다른 텍스트는 절대 포함하지 마세요:
{{
  "market_overview": "전체 시장 분위기를 2~3문장으로 친근하게 설명 (딱딱한 지표 수치 대신 상황을 이야기하듯)",
  "stocks": {{
    "NVDA": {{
      "summary": "이 종목의 현재 상황을 1~2문장, 친근한 말투로",
      "key_point": "지금 가장 중요한 포인트 한 줄 (예: 'RSI 30 이하로 떨어지면 진입 기회')"
    }}
  }}
}}

말투 규칙:
- 존댓말, 친근하게 (예: ~예요, ~해요, ~거예요)
- 수치는 꼭 필요한 것만 사용
- 어렵지 않게, 비전문가도 이해할 수 있도록
- 각 종목 summary는 60자 이내"""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1500,
        )
        raw = response.choices[0].message.content.strip()

        # JSON 파싱 (마크다운 코드블록 처리)
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        result = json.loads(raw)

        # 모든 ticker가 있는지 검증 후 없으면 빈 값 채우기
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
