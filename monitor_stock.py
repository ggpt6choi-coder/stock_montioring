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

            # 20일평균, 60일평균
            avg_20 = float(s.iloc[-20:].mean()) if len(s) >= 20 else price
            avg_60 = float(s.iloc[-60:].mean()) if len(s) >= 60 else price

            # 현재 MDD (최근 1년 최고점 대비)
            s_1y = s.loc[s.index >= str(today - pd.Timedelta(days=365))]
            max_1y = float(s_1y.max()) if not s_1y.empty else price
            cur_mdd = ((price - max_1y) / max_1y) * 100

            # 역사적 정석 연도별 평균 MDD (cummax)
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
                '20일평균': f"{avg_20:,.1f}" if not is_yield else '-',
                '60일평균': f"{avg_60:,.1f}" if not is_yield else '-',
                '현재MDD': f"{cur_mdd:.1f}%" if not is_yield else '-',
                '평균MDD': f"{avg_mdd:.1f}%" if (avg_mdd is not None and not is_yield) else '-',
                '연초대비': f"{ytd_change:+.1f}%" if not is_yield else '-',
                '_raw': {
                    'group_color': group_color,
                    'day_change': day_change,
                    'rsi': rsi_val,
                    'cur_mdd': cur_mdd,
                    'avg_mdd': avg_mdd,
                    'ytd': ytd_change,
                    'is_yield': is_yield
                }
            })

    if not results:
        print("생성할 데이터가 없습니다.")
        exit(0)

# 3. 테이블 드로잉 (원래의 선명하고 꽉 찬 1:1 정사각형 규격 복원)
    display_data = []
    row_colors = []
    
    for r in results:
        raw = r['_raw']
        row_colors.append(raw['group_color'])
        display_data.append({
            '티커': r['티커'],
            '현재가': r['현재가'],
            '전일대비': r['전일대비'],
            'RSI(14)': r['RSI(14)'],
            '20일평균': r['20일평균'],
            '60일평균': r['60일평균'],
            '현재MDD': r['현재MDD'],
            '평균MDD': r['평균MDD'],
            '연초대비': r['연초대비'],
        })

    df = pd.DataFrame(display_data)

    fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
    fig.patch.set_facecolor('#f8f9fa')
    ax.axis('off')

    nrows, ncols = df.shape
    created_row = ["" for _ in range(ncols)]
    table_data = [created_row, df.columns.tolist()] + df.values.tolist()

    table_bbox = [0.01, 0.01, 0.99, 0.99]
    table = ax.table(cellText=table_data, colLabels=None, loc='center', cellLoc='center', bbox=table_bbox)
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.0)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_edgecolor('none')
            cell.set_facecolor('#fff')
            cell.set_text_props(ha='right', va='center', color='blue', fontsize=10, weight='black')
            cell.set_height(0.07)
            if col == ncols - 1:
                cell.get_text().set_text(f"조회기준일시: {now_str}")
            else:
                cell.get_text().set_text("")
        elif row == 1:
            cell.set_facecolor('#444444')
            cell.set_fontsize(10.5)
            cell.set_text_props(weight='black', color='#fff', ha='center')
            cell.set_edgecolor('#ddd')
            cell.set_height(0.09)
        else:
            cell.set_edgecolor('#ddd')
            cell.set_height(0.09)
            data_row_idx = row - 2
            if 0 <= data_row_idx < len(row_colors):
                cell.set_facecolor(row_colors[data_row_idx])
            else:
                cell.set_facecolor('#ffffff')
            cell.set_fontsize(11)
            
            align = 'right' if col in [1,2,3,4,5,6,7,8] else 'center'
            if col in [0, 1]:
                cell.set_text_props(weight='black')
                
            if col == 2:  # 전일대비
                try:
                    v = float(cell.get_text().get_text().replace('%',''))
                    color = '#1976d2' if v < 0 else '#d32f2f'
                except:
                    color = '#222'
                cell.set_text_props(color=color, ha=align)
            elif col == 3:  # RSI
                try:
                    rsi = float(cell.get_text().get_text())
                    if rsi >= 70:
                        cell.set_text_props(color='#d32f2f', weight='bold', ha=align)
                    elif rsi <= 30:
                        cell.set_text_props(color='#1976d2', weight='bold', ha=align)
                    else:
                        cell.set_text_props(color='#222', ha=align)
                except:
                    cell.set_text_props(color='#222', ha=align)
            elif col == 4:  # 20일평균
                try:
                    a20 = float(cell.get_text().get_text().replace(',',''))
                    p = float(table[(row,1)].get_text().get_text().replace(',',''))
                    if a20 > p:
                        cell.set_text_props(color='#d32f2f', weight='heavy', ha=align)
                    else:
                        cell.set_text_props(color='#222', ha=align)
                except:
                    cell.set_text_props(color='#222', ha=align)
            elif col == 5:  # 60일평균
                try:
                    a60 = float(cell.get_text().get_text().replace(',',''))
                    p = float(table[(row,1)].get_text().get_text().replace(',',''))
                    if a60 > p:
                        cell.set_text_props(color='#d32f2f', weight='heavy', ha=align)
                    else:
                        cell.set_text_props(color='#222', ha=align)
                except:
                    cell.set_text_props(color='#222', ha=align)
            elif col == 6:  # 현재MDD
                try:
                    v = float(cell.get_text().get_text().replace('%',''))
                    color = '#d32f2f' if v <= -30 else '#222'
                    weight = 'heavy' if v <= -30 else 'normal'
                except:
                    color = '#222'
                    weight = 'normal'
                cell.set_text_props(color=color, weight=weight, ha=align)
            elif col == 7:  # 평균MDD (정석 값)
                try:
                    text7 = cell.get_text().get_text()
                    val7 = float(text7.replace('%',''))
                    text6 = table[(row,6)].get_text().get_text()
                    val6 = float(text6.replace('%',''))
                    # 현재 낙폭이 평균 낙폭보다 더 깊을 때 강조!
                    color = '#d32f2f' if val6 < val7 else '#222'
                    weight = 'heavy' if val6 < val7 else 'normal'
                except:
                    color = '#222'
                    weight = 'normal'
                cell.set_text_props(color=color, ha='right', weight=weight)
            elif col == 8:  # 연초대비
                try:
                    v = float(cell.get_text().get_text().replace('%',''))
                    color = '#d32f2f' if v > 0 else '#1976d2'
                except:
                    color = '#222'
                cell.set_text_props(color=color, ha='right')
            else:
                cell.set_text_props(color='#222', ha=align)

    # pad_inches=0으로 저장하여 여백 완전 제거 (1:1 꽉 찬 규격)
    plt.savefig('stock_monitoring_instagram.png', bbox_inches='tight', pad_inches=0, dpi=100)
    print('✅ 선명한 1:1 규격의 stock_monitoring_instagram.png 저장이 완료되었습니다.')

    # ---------------------------------------------------------
    # 기존 기능 유지 (다른 스크립트 연동 및 알림 전송)
    # ---------------------------------------------------------
    import subprocess
    import sys
    
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
            subject='[Daily Report] 주식 시장 모니터링',
            body='오늘의 종목, 지수 및 시장 심리/지도 리포트입니다.'
        )
        print('✅ 리포트 알림이 성공적으로 전송되었습니다.')
    except Exception as e:
        print(f"알림 전송 실패: {e}")
