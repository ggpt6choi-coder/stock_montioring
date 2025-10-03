import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

# AppleGothic 폰트 설정 (한글 깨짐 방지)
matplotlib.rc('font', family='AppleGothic')

def change_ticker_name(ticker):
    mapping = {
        "379780.KS": "RISE S&P500",
        "368590.KS": "RISE 미국나스닥100",
        "465580.KS": "ACE 미국빅테크TOP7 Plus",
        "458730.KS": "TIGER 미국배당다우존스",
        "305080.KS": "TIGER 미국국채10년",
        "484790.KS": "미국30년국채액티브(H)",
        "132030.KS": "KODEX 골드선물(H)"
    }
    return mapping.get(ticker, ticker)

def get_index_etf_info_yf():
    tickers = [
        "SPLG","VOO","SPY","SSO","UPRO",
        "379780.KS","QQQM","QQQ","QLD","TQQQ","368590.KS",
        "SCHD","458730.KS","IEF","UST","TYD","305080.KS",
        "TLT","UBT","TMF","484790.KS","IAUM","GLD","132030.KS"
    ]
    results = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="max", interval="1d")
            if hist.empty or 'Close' not in hist or 'High' not in hist:
                continue
            prices = hist['Close'].dropna()
            high_prices = hist['High'].dropna()
            current_price = prices.iloc[-1]
            all_time_high = high_prices.max()
            if ticker == "TMF":
                all_time_high /= 10
            all_time_high_gap = ((current_price - all_time_high) / all_time_high * 100)
            last20avg = prices[-20:].mean() if len(prices) >= 20 else prices.mean()
            last20_high = high_prices[-20:].max() if len(high_prices) >= 20 else high_prices.max()
            last20_high_gap = ((current_price - last20_high) / last20_high * 100)
            results.append({
                "티커": change_ticker_name(ticker),
                "현재가": f"{current_price:.1f}",
                "20일평균": f"{last20avg:.1f}",
                "20일최고점대비": f"{last20_high_gap:.1f}%",
                "전체고점": f"{all_time_high:.1f}",
                "전체고점대비": f"{all_time_high_gap:.1f}%"
            })
        except Exception as e:
            print(f"{ticker} 오류: {e}")

    df = pd.DataFrame(results)
    fig, ax = plt.subplots(figsize=(12, len(df)*0.5+2))
    ax.axis('off')
    table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.0, 1.0)
    plt.title('지수/ETF 모니터링', fontsize=16, weight='bold')
    plt.tight_layout()
    img_name = 'index_etf_monitoring.png'
    plt.savefig(img_name, bbox_inches='tight', dpi=120)
    print(f'지수 모니터링 이미지가 {img_name}로 저장되었습니다.')

if __name__ == "__main__":
    get_index_etf_info_yf()