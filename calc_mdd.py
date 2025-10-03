import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# 한글 폰트 설정 (macOS)
import matplotlib
matplotlib.rc('font', family='AppleGothic')


def calc_mdd(series):
    max_price = series.max()
    mdd = ((series.iloc[-1] - max_price) / max_price) * 100
    return mdd

# 일별 MDD 계산 함수
def daily_mdd(series):
    max_so_far = series.expanding().max()
    mdd = ((series - max_so_far) / max_so_far) * 100
    return mdd


def yearly_mdd(series):
    mdd_dict = {}
    df = series.to_frame('Close')
    df['Year'] = df.index.year
    for year, group in df.groupby('Year'):
        # 연도별 최고점 (해당 연도 내에서 발생한 최고점)
        max_price = group['Close'].max()
        # 연도 마지막 날의 주가
        last_price = group['Close'].iloc[-1]
        mdd = ((last_price - max_price) / max_price) * 100
        mdd_dict[year] = mdd
    return mdd_dict


def main():
    ticker = input('티커를 입력하세요: ').strip()
    stock = yf.Ticker(ticker)
    hist = stock.history(period="max")
    if hist.empty:
        print('데이터가 없습니다.')
        return
    now_price = hist['Close'].iloc[-1]
    mdd_now = calc_mdd(hist['Close'])
    mdd_daily = daily_mdd(hist['Close'])

    print(f"현재가: {now_price:.2f}")
    print(f"현재 기준 최고점 대비 MDD: {mdd_now:.2f}%")
    print("일별 MDD(상장일부터):")
    print(mdd_daily.tail())

    # 평균 MDD, 최고점 MDD 계산
    avg_mdd = mdd_daily.mean()
    max_mdd = mdd_daily.min()  # MDD는 음수값이 크면 낙폭이 큼
    print(f"평균 MDD: {avg_mdd:.2f}%")
    print(f"최고점(최대 낙폭) MDD: {max_mdd:.2f}%")

    # 일별 MDD 선그래프 시각화 및 이미지 저장
    plt.figure(figsize=(12,6))
    plt.plot(mdd_daily.index, mdd_daily.values, color='#1976d2', linewidth=1.5, label='일별 MDD')
    plt.axhline(avg_mdd, color='#ffa726', linestyle='--', linewidth=1.2, label=f'평균 MDD ({avg_mdd:.2f}%)')
    plt.axhline(max_mdd, color='#d32f2f', linestyle=':', linewidth=1.2, label=f'최대 낙폭 MDD ({max_mdd:.2f}%)')
    plt.title(f'{ticker} 일별 MDD (상장일부터)', fontsize=16, weight='bold')
    plt.xlabel('날짜', fontsize=13)
    plt.ylabel('MDD (%)', fontsize=13)
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    plt.legend(fontsize=12)
    plt.tight_layout()
    img_name = f'{ticker}_daily_mdd.png'
    plt.savefig(img_name, bbox_inches='tight', dpi=120)
    print(f'그래프 이미지가 {img_name}로 저장되었습니다.')
    plt.show()

if __name__ == "__main__":
    main()
    