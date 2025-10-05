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
ticker_name_map = {
    '^DJI': '다우존스',
    '^GSPC': 'S&P500',
    '^IXIC': 'NASDAQ',
    '^KS11': '코스피',
    'CL=F': 'WTI',
}
ticker_list = [
    '^DJI', '^GSPC', '^IXIC', '^KS11', 'CL=F',
    'IEF', 'TLT', 'GLD',
    'MSFT', 'META', 'NVDA', 'AMZN', 'GOOGL', 'AAPL', 'TSLA',
    'AVGO', 'ORCL', 'SMR', 'OKLO', 'PLTR', 'BMNR', 'HOOD', 'SNPS', 'BRK-B', 'WMT', 'O',
]

# yfinance로 종목 정보 가져오기
def fetch_stock_info(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    # 한글명 매핑 우선 적용
    name = ticker_name_map.get(ticker, info.get('shortName', ticker))
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 오늘, 하루전, 1주일전, 연초, 20일평균, 최고점
    today = datetime.now().date()
    start_of_year = datetime(today.year, 1, 1).date()
    hist = stock.history(period="1y")
    if hist.empty:
        print(f"데이터가 없습니다: {ticker}")
        return

    # 현재가 및 기준일자
    price = hist['Close'].iloc[-1]
    price_date = hist.index[-1].strftime('%Y-%m-%d')

    # 전일대비 변동율
    prev_day_price = hist['Close'].iloc[-2]
    day_change = ((price - prev_day_price) / prev_day_price) * 100
    # RSI(14) 계산
    def calc_rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    rsi_14 = calc_rsi(hist['Close']) if len(hist) >= 14 else None

    # 1주일전 주가
    week_ago_idx = len(hist) - 6 if len(hist) > 5 else 0
    week_ago_price = hist['Close'].iloc[week_ago_idx]

    # 1주일 변화율
    week_change = ((price - week_ago_price) / week_ago_price) * 100

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

    # 티커 칼럼에 주요 지수/원자재는 한글명으로 노출
    display_ticker = ticker_name_map.get(ticker, ticker)
    return {
        '티커': display_ticker, #0
        '현재가': f"{price:.1f}", #1
        '전일대비': f"{day_change:.2f}%", #2
        'RSI(14)': f"{rsi_14:.1f}" if rsi_14 else 'N/A', #3
        '20일평균': f"{avg_20:.1f}", #4
        '현재MDD': f"{mdd:.1f}%", #5
        '평균MDD': f"{calc_avg_mdd(ticker):.1f}%", #6
        '연초대비': f"{ytd_change:.1f}%" if year_start_price else 'N/A', #7
    }

# def send_image_via_gmail(sender_email, app_password, receiver_email, subject, body, image_path):
#     msg = MIMEMultipart()
#     msg['From'] = sender_email
#     msg['To'] = receiver_email
#     msg['Subject'] = subject
#     msg.attach(MIMEText(body, 'plain'))

#     with open(image_path, 'rb') as f:
#         mime = MIMEBase('image', 'png', filename=image_path)
#         mime.add_header('Content-Disposition', 'attachment', filename=image_path)
#         mime.add_header('X-Attachment-Id', '0')
#         mime.add_header('Content-ID', '<0>')
#         mime.set_payload(f.read())
#         encoders.encode_base64(mime)
#         msg.attach(mime)

#     server = smtplib.SMTP('smtp.gmail.com', 587)
#     server.starttls()
#     server.login(sender_email, app_password)
#     server.send_message(msg)
#     server.quit()
#     print('이미지 메일 전송 완료!')

def send_images_via_gmail(sender_email, app_password, receiver_email, subject, body, image_paths):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    for idx, image_path in enumerate(image_paths):
        with open(image_path, 'rb') as f:
            mime = MIMEBase('image', 'png', filename=os.path.basename(image_path))
            mime.add_header('Content-Disposition', 'attachment', filename=os.path.basename(image_path))
            mime.add_header('X-Attachment-Id', str(idx))
            mime.add_header('Content-ID', f'<{idx}>')
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
    for ticker in ticker_list:
        try:
            info = fetch_stock_info(ticker)
            if info:
                results.append(info)
        except Exception as e:
            print(f"{ticker} 오류: {e}")
    if results:
        df = pd.DataFrame(results)
        print(df.to_markdown(index=False))

    # 표만 이미지 전체에 꽉 차게 출력 (여백 최소화)
    fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
    fig.patch.set_facecolor('#f8f9fa')
    ax.axis('off')

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    nrows, ncols = df.shape
    created_row = ["" for _ in range(ncols)]
    table_data = [created_row, df.columns.tolist()] + df.values.tolist()
    # bbox: [left, bottom, right, top] - 표가 이미지에 최대한 꽉 차게
    table_bbox = [0.01, 0.01, 0.99, 0.99]
    table = ax.table(cellText=table_data, colLabels=None, loc='center', cellLoc='center', bbox=table_bbox)
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.0)

    # 표 스타일 개선 및 생성날짜 행 통합, border 제거
    for (row, col), cell in table.get_celld().items():
        # 생성날짜 행(맨 윗줄, row==0): 전체 통합처럼 보이게, 모든 셀 visible, cell 높이 최소화
        if row == 0:
            cell.set_edgecolor('none')
            cell.set_facecolor('#fff')
            cell.set_text_props(ha='right', va='center', color='blue', fontsize=10, weight='black')
            cell.set_height(0.07)
            if col == ncols-1:
                cell.get_text().set_text(f"조회기준일시: {now_str}")
            else:
                cell.get_text().set_text("")
        # 칼럼명 행(row==1): cell 높이 최소화
        elif row == 1:
            cell.set_facecolor('#444444')
            cell.set_fontsize(10)
            cell.set_text_props(weight='black', color='#fff', ha='center')
            cell.set_edgecolor('#ddd')
            cell.set_height(0.09)
        else:
            cell.set_edgecolor('#ddd')
            cell.set_height(0.09)
            # 오른쪽 정렬 컬럼 인덱스: 2(전일대비), 5(20일MDD), 6(최고점MDD), 7(연초대비)
            if 2 <= row <= 5:
                cell.set_facecolor('#E6F4FA')
            elif 6 <= row <= 9:
                cell.set_facecolor('#E9F9F0')
            else:
                cell.set_facecolor('#FFF4E6')
            cell.set_fontsize(11)

            align = 'right' if col in [2,5,6,7,8] else 'center'
            if col in [0,1]:
                cell.set_text_props(weight='black')
            if col == 2:
                try:
                    text = cell.get_text().get_text()
                    val = float(text.replace('%', ''))
                    color = '#1976d2' if val < 0 else '#d32f2f'
                except:
                    color = '#222'
                cell.set_text_props(color=color, ha=align)
            elif col == 3:
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
            elif col == 4:
                try:
                    avg_20 = float(cell.get_text().get_text())
                    price = float(table[(row,1)].get_text().get_text())
                    if avg_20 > price:
                        cell.set_text_props(color='#1976d2', weight='heavy', ha=align)
                    else:
                        cell.set_text_props(color='#222', ha=align)
                except:
                    cell.set_text_props(color='#222', ha=align)
            elif col == 5:
                try:
                    text = cell.get_text().get_text()
                    val = float(text.replace('%', ''))
                    color = '#1976d2' if val <= -30 else '#222'
                    weight = 'black' if val <= -30 else 'normal'
                except:
                    color = '#222'
                    weight = 'normal'
                cell.set_text_props(color=color, weight=weight, ha=align)
            elif col == 6:
                try:
                    text6 = cell.get_text().get_text()
                    val6 = float(text6.replace('%', ''))
                    # col==5(현재MDD) 값 가져오기
                    text5 = table[(row,5)].get_text().get_text()
                    val5 = float(text5.replace('%', ''))
                    color = '#1976d2' if val6 > val5 else '#222'
                except:
                    color = '#222'
                cell.set_text_props(color=color, ha='right')
            elif col == 7:
                try:
                    text = cell.get_text().get_text()
                    val = float(text.replace('%', ''))
                    color = '#d32f2f' if val > 0 else '#1976d2'
                except:
                    color = '#222'
                cell.set_text_props(color=color, ha='right')
            else:
                cell.set_text_props(color='#222', ha=align)

    # pad_inches=0으로 저장하여 여백 완전 제거
    plt.savefig('stock_monitoring_instagram.png', bbox_inches='tight', pad_inches=0, dpi=100)
    print('인스타그램용 이미지가 stock_monitoring_instagram.png로 저장되었습니다.')

    
    import subprocess
    subprocess.run(['python3', 'monitor_index.py'], cwd=os.path.dirname(os.path.abspath(__file__)))

    load_dotenv()
    SENDER_EMAIL = os.getenv('SENDER_EMAIL')
    APP_PASSWORD = os.getenv('APP_PASSWORD')
    RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')

    send_images_via_gmail(
        sender_email=SENDER_EMAIL,
        app_password=APP_PASSWORD,
        receiver_email=RECEIVER_EMAIL,
        subject='주식 테이블 이미지',
        body='첨부된 이미지를 확인하세요.',
        image_paths=['stock_monitoring_instagram.png', 'index_monitoring_instagram.png']
    )


    # load_dotenv()
    # SENDER_EMAIL = os.getenv('SENDER_EMAIL')
    # APP_PASSWORD = os.getenv('APP_PASSWORD')
    # RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
    
    # send_image_via_gmail(
    #     sender_email=SENDER_EMAIL,
    #     app_password=APP_PASSWORD,
    #     receiver_email=RECEIVER_EMAIL,
    #     subject='주식 테이블 이미지',
    #     body='첨부된 이미지를 확인하세요.',
    #     image_path='stock_table_instagram.png'
    # )
else:
    print("데이터가 없습니다.")
