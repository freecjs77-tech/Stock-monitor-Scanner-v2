import yfinance as yf, time, json

tk = yf.Ticker("NVDA")
news = tk.news or []
print(f"총 뉴스 수: {len(news)}")
if news:
    print("\n--- 첫 번째 뉴스 구조 ---")
    print(json.dumps(news[0], indent=2, default=str))
    print("\n--- 모든 뉴스 타임스탬프 ---")
    now = time.time()
    for i, n in enumerate(news[:10]):
        ts = n.get('providerPublishTime', 0)
        diff_days = (now - ts) / 86400
        print(f"[{i}] {diff_days:.1f}일 전  |  {n.get('title','')[:60]}")
