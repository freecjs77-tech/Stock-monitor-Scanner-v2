#!/usr/bin/env python3
import sys, os, traceback, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cowork_agents'))

try:
    from report_engine import generate_report

    test_stock = {
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
        'price_path': [(0,112),(25,86.62),(80,130),(145,212.19),(190,195),(220,178),(245,175),(261,172.70)],
    }
    out_dir = os.path.join(os.path.dirname(__file__), 'test_output')
    os.makedirs(out_dir, exist_ok=True)
    path = generate_report(test_stock, out_dir)
    print(f'SUCCESS: {path}')
    print(f'Size: {os.path.getsize(path)} bytes')

except Exception:
    traceback.print_exc()
    sys.exit(1)
