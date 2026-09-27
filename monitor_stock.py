import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
import os
import platform
import math
from notifier import notify

#OS판별
system_name = platform.system()

if system_name == 'Darwin':  # macOS
    matplotlib.rc('font', family='AppleGothic')
elif system_name == 'Linux':  # GitHub Actions 등 Ubuntu 환경
    matplotlib.rc('font', family='NanumGothic')



# 여러 종목 코드 리스트
ticker_name_map = {
    '^DJI': '다우존스',
    '^GSPC': 'S&P500',
    '^IXIC': 'NASDAQ',
    '^KS11': '코스피',
    'CL=F': 'WTI(원유)',
    '^TNX': '미 10년물',
    '^TYX': '미 30년물',
    'GLD': 'GLD(금)'
}

# 종목 그룹 정의 (배경색 구분을 위해 color 속성 추가)
ticker_groups = [
    {
        "name": "지수",
        "tickers": ['^DJI', '^GSPC', '^IXIC', '^KS11'],
        "color": "#f8fafc" # Slate-50 (연한 푸른빛/회색)
    },
    {
        "name": "금리 및 원자재",
        "tickers": ['^TNX', '^TYX', 'CL=F', 'GLD'],
        "color": "#fffbeb" # Amber-50 (연한 노랑)
    },
    {
        "name": "M7기업",
        "tickers": ['MSFT', 'META', 'NVDA', 'AMZN', 'GOOGL', 'AAPL', 'TSLA'],
        "color": "#f0fdf4" # Green-50 (연한 초록)
    },
    {
        "name": "기타기업",
        "tickers": ['AVGO', 'TSM', 'SNPS', 'VST', 'SMR', 'OKLO', 'RKLB', 'PLTR', 'BMNR', 'HOOD', 'BRK-B', 'LLY', 'O'],
        "color": "#ffffff" # White (기본 흰색)
    }
]

def safe_float(val):
    if val is None or pd.isna(val):
        return None
    try:
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            return None
        return f_val
    except:
        return None

def calc_rsi(series, period=14):
    if len(series) < period: return None
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return safe_float(rsi.iloc[-1])

def calc_historical_avg_mdd(series: pd.Series) -> float:
    """정석 퀀트 공식 기반 상장 이후 연도별 평균 MDD 계산 (cummax 활용)"""
    s = series.dropna()
    if len(s) < 50:
        return None
    df = s.to_frame('Close')
    df['Year'] = df.index.year
    mdds = []
    for year, group in df.groupby('Year'):
        p = group['Close']
        if len(p) < 5:
            continue
        rolling_max = p.cummax()
        drawdown = (p - rolling_max) / rolling_max * 100
        mdds.append(drawdown.min())
    return float(np.mean(mdds)) if mdds else None


if __name__ == "__main__":
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today = datetime.now().date()
    start_of_year = datetime(today.year, 1, 1).date()

    # 전체 종목 수집
    all_tickers = []
    for group in ticker_groups:
        all_tickers.extend(group['tickers'])

    print(f"1. {len(all_tickers)}개 종목 전체 역사적 일봉 데이터 일괄 수집 중...")
    try:
        raw = yf.download(all_tickers, period="max", auto_adjust=True, progress=False)
        closes = raw['Close']
    except Exception as e:
        print(f"데이터 다운로드 실패: {e}")
        exit(1)

    print("2. 종목별 정석 역사적 평균 MDD 및 기술 지표 계산 중...")
    avg_mdd_map = {}
    for tk in all_tickers:
        if tk in closes.columns:
            s_close = closes[tk].dropna()
            avg_mdd_val = calc_historical_avg_mdd(s_close)
            if avg_mdd_val is not None:
                avg_mdd_map[tk] = avg_mdd_val

    results = []
    for group in ticker_groups:
        group_color = group['color']
        for tk in group['tickers']:
            if tk not in closes.columns:
                continue
            s = closes[tk].dropna()
            if len(s) < 2:
                continue

            price = float(s.iloc[-1])
            prev_price = float(s.iloc[-2])
            day_change = ((price - prev_price) / prev_price) * 100

            # RSI(14)
            delta = s.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi_val = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None

            # 20일선 이격률 (%)
            avg_20 = float(s.iloc[-20:].mean()) if len(s) >= 20 else price
            gap_20 = ((price - avg_20) / avg_20) * 100

            # 현재 MDD (최근 1년 최고점 대비)
            s_1y = s.loc[s.index >= str(today - pd.Timedelta(days=365))]
            max_1y = float(s_1y.max()) if not s_1y.empty else price
            cur_mdd = ((price - max_1y) / max_1y) * 100

            # 역사적 정석 연도별 평균 MDD
            avg_mdd = avg_mdd_map.get(tk, None)

            # 연초 대비 수익률 (YTD)
            s_ytd = s.loc[s.index >= str(start_of_year)]
            first_ytd = float(s_ytd.iloc[0]) if not s_ytd.empty else price
            ytd_change = ((price - first_ytd) / first_ytd) * 100

            is_yield = tk in ['^TNX', '^TYX']
            display_ticker = ticker_name_map.get(tk, tk)

            results.append({
                '티커': display_ticker,
                '현재가': f"{price:,.2f}" if (price < 100 or is_yield) else f"{price:,.1f}",
                '전일대비': f"{day_change:+.1f}%",
                'RSI(14)': f"{rsi_val:.1f}" if rsi_val is not None else '-',
                '20일선': f"{gap_20:+.1f}%",
                '현재MDD': f"{cur_mdd:.1f}%" if not is_yield else '-',
                '평균MDD': f"{avg_mdd:.1f}%" if (avg_mdd is not None and not is_yield) else '-',
                '연초대비': f"{ytd_change:+.1f}%" if not is_yield else '-',
                '_raw': {
                    'group_color': group_color,
                    'day_change': day_change,
                    'rsi': rsi_val,
                    'gap_20': gap_20,
                    'cur_mdd': cur_mdd,
                    'avg_mdd': avg_mdd,
                    'ytd': ytd_change,
                    'is_yield': is_yield
                }
            })

    if not results:
        print("생성할 데이터가 없습니다.")
        exit(0)

    # 3. 테이블 드로잉
    display_data = [{k: v for k, v in r.items() if k != '_raw'} for r in results]
    df = pd.DataFrame(display_data)

    fig, ax = plt.subplots(figsize=(11, 13.5), dpi=120)
    fig.patch.set_facecolor('#ffffff')
    ax.set_position([0.02, 0.05, 0.96, 0.88])
    ax.axis('off')

    colnames = df.columns.tolist()
    table_data = [colnames] + df.values.tolist()

    table = ax.table(cellText=table_data, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(13)

    header_color = '#1e293b'
    border_color = '#cbd5e1'

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(border_color)
        cell.set_linewidth(0.8)

        if row == 0:
            cell.set_facecolor(header_color)
            cell.set_text_props(weight='bold', color='#ffffff', size=13.5)
            cell.set_height(0.045)
        else:
            cell.set_height(0.032)
            raw = results[row - 1]['_raw']
            base_color = raw['group_color']
            cell.set_facecolor(base_color)
            val_text = cell.get_text().get_text()

            # 정렬 및 서식
            if col == 0:
                cell.set_text_props(ha='left', weight='bold', color='#0f172a')
                cell.get_text().set_text(f"  {val_text}")
            elif col == 1:
                cell.set_text_props(ha='right', weight='bold', color='#1e293b')
                cell.get_text().set_text(f"{val_text}  ")
            else:
                cell.set_text_props(ha='right')
                cell.get_text().set_text(f"{val_text}  ")

                # 조건부 하이라이트
                if col == colnames.index('전일대비'):
                    v = raw['day_change']
                    if not raw['is_yield'] and v is not None:
                        if v > 0:
                            cell.set_text_props(color='#ef4444', weight='bold')
                            if v >= 2.5: cell.set_facecolor('#fef2f2')
                        elif v < 0:
                            cell.set_text_props(color='#3b82f6', weight='bold')
                            if v <= -2.5: cell.set_facecolor('#eff6ff')

                elif col == colnames.index('RSI(14)'):
                    r = raw['rsi']
                    if r is not None:
                        if r >= 70:
                            cell.set_text_props(color='#ef4444', weight='bold')
                            cell.set_facecolor('#fef2f2')
                        elif r <= 30:
                            cell.set_text_props(color='#3b82f6', weight='bold')
                            cell.set_facecolor('#eff6ff')

                elif col == colnames.index('20일선'):
                    g = raw['gap_20']
                    if g is not None:
                        cell.set_text_props(color='#ef4444' if g > 0 else '#3b82f6')

                elif col == colnames.index('현재MDD'):
                    cm = raw['cur_mdd']
                    am = raw['avg_mdd']
                    if cm is not None:
                        # 현재 낙폭이 역사적 평균 낙폭보다 더 깊을 때 (과대낙폭 구간 강조)
                        if am is not None and cm < am:
                            cell.set_text_props(color='#dc2626', weight='bold')
                            cell.set_facecolor('#fef2f2')
                        elif cm <= -25:
                            cell.set_text_props(color='#ef4444')

                elif col == colnames.index('평균MDD'):
                    cell.set_text_props(color='#64748b')

                elif col == colnames.index('연초대비'):
                    y = raw['ytd']
                    if not raw['is_yield'] and y is not None:
                        cell.set_text_props(color='#ef4444' if y > 0 else '#3b82f6')

    # 상단 헤더 & 하단 설명
    plt.figtext(0.02, 0.955, "[Daily Market Monitor]", fontsize=22, weight='bold', ha='left', color='#0f172a')
    plt.figtext(0.98, 0.955, f"조회기준: {now_str}", fontsize=13, ha='right', color='#64748b')

    legend_text = "* 20일선: 20일 이평선 이격률(%) | 평균MDD: 역사적 연도별 최대낙폭 평균 (현재MDD가 평균보다 깊을 시 붉은색 강조)"
    plt.figtext(0.02, 0.015, legend_text, fontsize=11, color='#64748b', ha='left')

    plt.savefig('stock_monitoring_instagram.png', bbox_inches='tight', pad_inches=0.1, dpi=120)
    print('✅ 개선된 데일리 리포트 이미지가 stock_monitoring_instagram.png로 저장되었습니다.')

    # ---------------------------------------------------------
    # 기존 기능 유지 (다른 스크립트 연동 및 이메일 전송)
    # ---------------------------------------------------------
    import subprocess
    import sys
    
    # monitor_index.py 도 같이 실행 (원할 경우 UI 통일 패치 필요)
    try:
        subprocess.run([sys.executable, 'monitor_index.py'], cwd=os.path.dirname(os.path.abspath(__file__)))
    except Exception as e:
        print(f"monitor_index.py 실행 실패: {e}")

    load_dotenv()
    # 시장 심리 지표 및 맵 생성
    try:
        from monitor_sentiment import create_sentiment_image
        create_sentiment_image('sentiment_monitoring.png')
    except Exception as e:
        print(f"sentiment_monitoring.png 생성 실패: {e}")

    try:
        from monitor_map import capture_market_map
        capture_market_map('market_map.png')
    except Exception as e:
        print(f"시장 맵 생성 실패: {e}")

    # 모든 이미지를 모아서 한 번에 전송
    image_list = [
        'stock_monitoring_instagram.png', 
        'index_monitoring_instagram.png', 
        'sentiment_monitoring.png'
    ]
    if os.path.exists('market_map.png'):
        image_list.append('market_map.png')

    try:
        notify(
            image_paths=image_list,
            subject='[Daily Report] 주식 시장 모니터링 (UI 개선판)',
            body='오늘의 종목, 지수 및 시장 심리/지도 리포트입니다. (UI 개선 버전 적용)'
        )
        print('✅ 리포트 알림이 성공적으로 전송되었습니다.')
    except Exception as e:
        print(f"알림 전송 실패: {e}")
