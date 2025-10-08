import yfinance as yf
import pandas as pd
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

#OS판별
system_name = platform.system()

if system_name == 'Darwin':  # macOS
    matplotlib.rc('font', family='AppleGothic')
elif system_name == 'Linux':  # GitHub Actions 등 Ubuntu 환경
    matplotlib.rc('font', family='NanumGothic')

# macOS 기본 한글 폰트 설정 (AppleGothic)
# matplotlib.rc('font', family='AppleGothic')
# matplotlib.rc('font', family='NanumGothic')

# 평균 MDD, 최대 MDD 계산 예시 (calc_mdd.py 참고)
def daily_mdd(series):
    max_so_far = series.expanding().max()
    mdd = ((series - max_so_far) / max_so_far) * 100
    return mdd

def calc_avg_mdd(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="max")
    mdd_daily = daily_mdd(hist['Close'])
    avg_mdd = mdd_daily.mean()
    return avg_mdd

# 여러 종목 코드 리스트 (지수/ETF/원자재/주식)

# 카테고리별 종목 리스트 및 한글명 매핑

# (검색용 티커, 표에 표시할 이름) 쌍으로 구성
category_map = [
    ("S&P500", [
        ("SPLG", "SPLG"), ("SPY", "SPY"), ("SSO", "SSO"), ("UPRO", "UPRO"), ("453330.KS", "RISE S&P500")
    ]),
    ("NASDAQ", [
        ("QQQM", "QQQM"), ("QQQ", "QQQ"), ("QLD", "QLD"), ("TQQQ", "TQQQ"), ("368590.KS", "RESE미국나스닥100")
    ]),
    ("배당성장", [
        ("SCHD", "SCHD"), ("458730.KS", "TIGER미국배우당다우존스")
    ]),
    ("중기채", [
        ("IEF", "IEF"), ("UST", "UST"), ("TYD", "TYD"), ("305080.KS", "TIGER미국국채10년")
    ]),
    ("장기채", [
        ("TLT", "TLT"), ("UBT", "UBT"), ("TMF", "TMF"), ("481340.KS", "RISE 미국30년국채액티브")
    ]),
    ("금", [
        ("GLDM", "GLDM"), ("0072R0.KS", "TIGER KRX금현물")
    ]),
]

# 표에 표시할 이름을 매핑 (검색용 티커 → 표에 표시할 이름)
ticker_name_map = {
    "SPLG": "SPLG",
    "SPY": "SPY",
    "SSO": "SSO",
    "UPRO": "UPRO",
    "453330.KS": "RISE S&P500",
    "QQQM": "QQQM",
    "QQQ": "QQQ",
    "QLD": "QLD",
    "TQQQ": "TQQQ",
    "368590.KS": "RESE미국나스닥100",
    "SCHD": "SCHD",
    "458730.KS": "TIGER미국배우당다우존스",
    "IEF": "IEF",
    "UST": "UST",
    "TYD": "TYD",
    "305080.KS": "TIGER미국국채10년",
    "TLT": "TLT",
    "UBT": "UBT",
    "TMF": "TMF",
    "481340.KS": "RISE 미국30년국채액티브",
    "GLDM": "GLDM",
    "0072R0.KS": "TIGER KRX금현물",
}

# yfinance로 종목 정보 가져오기
def fetch_stock_info(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    name = ticker_name_map.get(ticker, info.get('shortName', ticker))
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    today = datetime.now().date()
    start_of_year = datetime(today.year, 1, 1).date()
    hist = stock.history(period="1y")
    if hist.empty:
        print(f"데이터가 없습니다: {ticker}")
        return

    price = hist['Close'].iloc[-1]
    price_date = hist.index[-1].strftime('%Y-%m-%d')

    # 20일평균
    avg_20 = hist['Close'][-20:].mean() if len(hist) >= 20 else hist['Close'].mean()

    # 연초 주가
    year_start_price = hist.loc[hist.index >= str(start_of_year), 'Close']
    if not year_start_price.empty:
        year_start_price = year_start_price.iloc[0]
        ytd_change = ((price - year_start_price) / year_start_price) * 100
    else:
        year_start_price = None
        ytd_change = None

    # 최고점, 최고점 날짜, MDD
    max_price = hist['Close'].max()
    max_price_idx = hist['Close'].idxmax()
    max_price_date = max_price_idx.strftime('%Y-%m-%d')
    mdd = ((price - max_price) / max_price) * 100

    # 20일 MDD 계산
    max_20 = hist['Close'][-20:].max() if len(hist) >= 20 else hist['Close'].max()
    mdd_20 = ((price - max_20) / max_20) * 100

    display_ticker = ticker_name_map.get(ticker, ticker)
    return {
        '티커': display_ticker, #0
        '현재가': f"{price:,.1f}", #1
        '20일평균': f"{avg_20:.1f}", #2
        '20일MDD': f"{mdd_20:.1f}%", #4
        '현재MDD': f"{mdd:.1f}%", #3
        '연초대비': f"{ytd_change:.1f}%" if year_start_price else 'N/A', #5
    }

def send_image_via_gmail(sender_email, app_password, receiver_email, subject, body, image_path):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    with open(image_path, 'rb') as f:
        mime = MIMEBase('image', 'png', filename=image_path)
        mime.add_header('Content-Disposition', 'attachment', filename=image_path)
        mime.add_header('X-Attachment-Id', '0')
        mime.add_header('Content-ID', '<0>')
        mime.set_payload(f.read())
        encoders.encode_base64(mime)
        msg.attach(mime)

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, app_password)
    server.send_message(msg)
    server.quit()
    print('이미지 메일 전송 완료!')


if __name__ == "__main__":
    results = []
    table_data = []
    colnames = None
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 카테고리별로 표 데이터 생성
    # 표의 첫 번째 열에 카테고리(구분값) 추가
    for cat, ticker_pairs in category_map:
        for ticker, display_name in ticker_pairs:
            try:
                info = fetch_stock_info(ticker)
                if info:
                    # 상품명(표시명) 칼럼을 항상 두 번째로 추가
                    row = [cat, display_name]
                    # info에서 '티커' 항목을 제외한 나머지 값만 추가
                    row += [v for k, v in info.items() if k != "티커"]
                    if colnames is None:
                        # 칼럼명: 구분, 상품명, 나머지 info.keys() (티커 제외)
                        keys = [k for k in info.keys() if k != "티커"]
                        # '평균MDD' 대신 '20일MDD'가 포함됨
                        colnames = ["구분", "상품명"] + keys
                    table_data.append(row)
            except Exception as e:
                print(f"{ticker} 오류: {e}")

    if table_data and colnames:
        # 생성날짜 행 추가
        created_row = ["" for _ in range(len(colnames))]
        table_data = [created_row, colnames] + table_data

        fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
        fig.patch.set_facecolor('#f8f9fa')
        ax.axis('off')

        nrows, ncols = len(table_data), len(colnames)
        table_bbox = [0.01, 0.01, 0.99, 0.99]
        table = ax.table(cellText=table_data, colLabels=None, loc='center', cellLoc='center', bbox=table_bbox)
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.0, 1.0)

        # 표 스타일 개선 및 생성날짜 행 통합, border 제거
        # 카테고리별 배경색 정의
        # 중복 없는 6가지 계열 색상 (파랑, 초록, 노랑, 주황, 분홍, 보라)
        category_colors = [
            "#e3f0ff",  # 연파랑
            "#e6f7e6",  # 연초록
            "#fff7e3",  # 연노랑
            "#ffe9e3",  # 연주황
            "#fbe3ff",  # 연분홍
            "#ece3ff"   # 연보라
        ]

        # 카테고리별로 색상 적용을 위해 각 행의 카테고리 인덱스 추출
        cat_indices = []
        prev_cat = None
        cat_idx = -1
        for row in range(2, nrows):
            cat = table[(row,0)].get_text().get_text()
            if cat != '' and cat != prev_cat:
                cat_idx += 1
                prev_cat = cat
            cat_indices.append(cat_idx)

        for (row, col), cell in table.get_celld().items():
            # 셀 스타일(정렬, weight, 병합 등) 기존대로 적용
            if row == 0:
                cell.set_edgecolor('none')
                cell.set_facecolor('#fff')
                cell.set_text_props(ha='right', va='center', color='blue', fontsize=10, weight='black')
                cell.set_height(0.07)
                if col == ncols-1:
                    cell.get_text().set_text(f"조회기준일시: {now_str}")
                else:
                    cell.get_text().set_text("")
            elif row == 1:
                cell.set_facecolor('#444444')
                cell.set_fontsize(10)
                cell.set_text_props(weight='black', color='#fff', ha='center')
                cell.set_edgecolor('#ddd')
                cell.set_height(0.09)
                if col == 1:
                    cell.set_width(0.32)
            elif row >= 2:
                cat_idx = cat_indices[row-2] if (row-2) < len(cat_indices) else 0
                cell.set_facecolor(category_colors[cat_idx % len(category_colors)])
                cell.set_height(0.09)
                cell.set_fontsize(11)
                if col == 1:
                    cell.set_width(0.32)

            # 텍스트 색상 조건부 적용 (스타일과 분리)
            if row >= 2 and colnames is not None and col < len(colnames):
                colname = colnames[col]
                val = cell.get_text().get_text().replace('%','').replace(',','')
                # '구분', '상품명' 칼럼이 아니면 우측정렬
                if colname not in ['구분', '상품명']:
                    cell.set_text_props(ha='right')
                # 20일MDD 파랑색
                if colname == '20일MDD':
                    try:
                        if float(val) <= -5:
                            cell.get_text().set_color('red')
                    except:
                        pass
                # 현재가 < 20일평균 파랑색
                if colname == '20일평균':
                    try:
                        price = float(val)
                        nowPrice = table[(row, colnames.index('현재가'))].get_text().get_text().replace(',','')
                        if float(price) > float(nowPrice):
                            cell.get_text().set_color('red')
                    except:
                        pass
                if colname == '연초대비':
                    try:
                        price = float(val)
                        color = '#1976d2' if price < 0 else '#d32f2f'
                        cell.set_text_props(color=color)
                    except:
                        pass
                if row == 2:
                    cell.set_facecolor("#90caf9")
                    cell.set_text_props(weight='900')
                if row == 7:
                    cell.set_facecolor("#81c784")
                    cell.set_text_props(weight='900')
                if row == 12:
                    cell.set_facecolor("#ffe082")
                    cell.set_text_props(weight='900')
                if row == 14:
                    cell.set_facecolor("#ffb74d")
                    cell.set_text_props(weight='900')
                if row == 18:
                    cell.set_facecolor("#f48fb1")
                    cell.set_text_props(weight='900')
                if row == 22:
                    cell.set_facecolor("#b39ddb")
                    cell.set_text_props(weight='900')

        # 구분(카테고리) 값이 연속되는 행은 첫 행만 표시, 나머지는 빈 문자열로
        prev_cat = None
        for row in range(2, nrows):
            cat = table[(row,0)].get_text().get_text()
            if cat == prev_cat:
                table[(row,0)].get_text().set_text("")
            else:
                prev_cat = cat

        plt.savefig('index_monitoring_instagram.png', bbox_inches='tight', pad_inches=0, dpi=100)
        print('인스타그램용 이미지가 index_monitoring_instagram.png로 저장되었습니다.')

    
    load_dotenv()
    SENDER_EMAIL = os.getenv('SENDER_EMAIL')
    APP_PASSWORD = os.getenv('APP_PASSWORD')
    RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
    
    # send_image_via_gmail(
    #     sender_email=SENDER_EMAIL,
    #     app_password=APP_PASSWORD,
    #     receiver_email=RECEIVER_EMAIL,
    #     subject='주식 테이블 이미지',
    #     body='첨부된 이미지를 확인하세요.',
    #     image_path='index_monitoring_instagram.png'
    # )
else:
    print("데이터가 없습니다.")
