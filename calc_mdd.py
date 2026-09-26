import warnings
warnings.filterwarnings('ignore')

import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rc('font', family='AppleGothic')


# ─────────────────────────────────────────────
# 공식 1: 전체 기간 MDD (현재 기준)
# ─────────────────────────────────────────────

def calc_mdd(series: pd.Series) -> float:
    """
    상장 이후 전체 기간의 MDD.

    rolling_max: 매일 '그 날까지의 누적 최고가'를 갱신
    drawdown:    오늘 가격이 누적 최고가에서 얼마나 빠졌는가

    공식: (현재가 - 누적고점) / 누적고점 × 100
    최솟값 = 역사상 가장 깊이 빠진 순간 = MDD
    """
    rolling_max = series.cummax()
    drawdown    = (series - rolling_max) / rolling_max * 100
    return drawdown.min()


# ─────────────────────────────────────────────
# 공식 2: 일별 Drawdown 시계열
# ─────────────────────────────────────────────

def daily_drawdown(series: pd.Series) -> pd.Series:
    """
    매 거래일마다 '그 시점 누적 고점 대비 낙폭(%)'을 반환.

    예) 누적고점 100 → 오늘 80 → drawdown = -20%
        누적고점 100 → 오늘 110(신고가) → drawdown = 0%

    이 시계열의 min() = 해당 기간 MDD
    """
    rolling_max = series.cummax()   # expanding max = 누적 최고점
    drawdown    = (series - rolling_max) / rolling_max * 100
    return drawdown


# ─────────────────────────────────────────────
# 공식 3: 연도별 MDD + Total Return (핵심 수정)
# ─────────────────────────────────────────────

def yearly_stats(series: pd.Series) -> pd.DataFrame:
    """
    연도별 MDD와 Total Return을 계산하여 DataFrame으로 반환.

    [MDD 공식]
    - 연도 내 매 거래일마다 '그 날까지의 연중 누적 고점' 계산 (cummax)
    - drawdown = (당일가 - 연중누적고점) / 연중누적고점 × 100
    - 그 해 가장 낮은 drawdown = 그 해 MDD

    [이전 코드의 문제]
    - 연말 종가 vs 연중 최고가 → 연말에 반등하면 MDD가 축소됨
    - 예) 고점 100 → 저점 60 → 연말 90 이면
        이전 코드: (90-100)/100 = -10%  ← 실제 낙폭보다 작게 나옴
        올바른 MDD: (60-100)/100 = -40% ← 실제로 최대 40% 빠진 것

    [Total Return 공식]
    - 연초 첫 거래일 종가 → 연말 마지막 거래일 종가 변화율
    - TR = (연말 종가 - 연초 종가) / 연초 종가 × 100
    - yfinance auto_adjust=True(수정주가) 데이터를 쓰면
      배당·분할이 반영된 진짜 Total Return이 됨
    """
    records = []

    df = series.to_frame('Close')
    df.index = pd.to_datetime(df.index)
    df['Year'] = df.index.year

    for year, group in df.groupby('Year'):
        prices = group['Close'].dropna()
        if len(prices) < 5:   # 데이터가 너무 적은 해 제외
            continue

        # ── MDD: cummax 기반 rolling drawdown ──────────────
        rolling_max = prices.cummax()
        drawdown    = (prices - rolling_max) / rolling_max * 100
        mdd         = drawdown.min()

        # ── Total Return: 연초 → 연말 ──────────────────────
        first_price = prices.iloc[0]
        last_price  = prices.iloc[-1]
        total_return = (last_price - first_price) / first_price * 100

        records.append({
            'Year':             year,
            'Max Drawdown (%)': round(mdd, 2),
            'Total Return (%)': round(total_return, 2),
        })

    result = pd.DataFrame(records).set_index('Year')

    # 평균 행 추가
    avg_row = pd.DataFrame(
        [[result['Max Drawdown (%)'].mean().round(2),
          result['Total Return (%)'].mean().round(2)]],
        columns=['Max Drawdown (%)', 'Total Return (%)'],
        index=['평균'],
    )
    return pd.concat([result, avg_row])


# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# 공식 4: 캡처 스타일 표(Table) 이미지 생성
# ─────────────────────────────────────────────

def save_table_image(ticker: str, stats: pd.DataFrame, start_date: str, end_date: str) -> str:
    """
    캡처해 주신 책/리포트 디자인과 동일한 고품질 표(Table) 이미지를 생성합니다.
    """
    matplotlib.rc('font', family='AppleGothic')
    matplotlib.rcParams['axes.unicode_minus'] = False

    # 데이터 준비
    col_labels = ['Year', 'Max Drawdown (%)', 'Total Return (%)']
    
    # 마지막 '평균' 행 분리
    data_rows = stats.iloc[:-1]
    avg_row = stats.iloc[-1]

    cell_text = []
    for year_idx, row in data_rows.iterrows():
        cell_text.append([
            str(year_idx),
            f"{row['Max Drawdown (%)']:.2f}",
            f"{row['Total Return (%)']:.2f}",
        ])
    # 평균 행 추가
    cell_text.append([
        '평균',
        f"{avg_row['Max Drawdown (%)']:.2f}",
        f"{avg_row['Total Return (%)']:.2f}",
    ])

    n_rows = len(cell_text)
    fig_height = max(7.0, n_rows * 0.32 + 2.2)
    fig, ax = plt.subplots(figsize=(6.2, fig_height), facecolor='white')
    ax.axis('off')

    # 상단 헤더 텍스트 (책 디자인 재현)
    fig.text(0.08, 0.965, '❶', fontsize=16, fontweight='bold', color='#ea580c', family='AppleGothic')
    fig.text(0.125, 0.965, f'{ticker}', fontsize=16, fontweight='bold', color='#166534', family='AppleGothic')
    fig.text(0.08, 0.942, '최대낙폭(MDD) 평균 및 연도별 최종수익률(TR)', fontsize=13.5, fontweight='bold', color='#166534', family='AppleGothic')
    fig.text(0.08, 0.920, f'{start_date} ~ {end_date}', fontsize=10.5, color='#22c55e', family='AppleGothic')

    # 테이블 생성
    table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        cellLoc='center',
        loc='center',
        bbox=[0.05, 0.03, 0.90, 0.86]
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10.5)

    # 스타일링: 세로 테두리 제거, 가로선 및 헤더 강조
    header_bg = '#dce8f8'
    row_line_color = '#cbd5e1'

    for (r, c), cell in table.get_celld().items():
        cell.set_linewidth(0)
        
        if r == 0:  # 컬럼 헤더
            cell.set_facecolor(header_bg)
            cell.set_text_props(weight='bold', color='#0f172a', size=11)
            cell.visible_edges = 'TB'
            cell.set_edgecolor('#64748b')
            cell.set_linewidth(1.2)
        elif r == n_rows:  # 마지막 평균 행
            cell.set_facecolor('white')
            cell.set_text_props(weight='bold', color='#0f172a', size=11)
            cell.visible_edges = 'B'
            cell.set_edgecolor('#64748b')
            cell.set_linewidth(1.5)
        else:  # 일반 데이터 행
            cell.set_facecolor('white')
            cell.set_text_props(color='#1e293b')
            cell.visible_edges = 'B'
            cell.set_edgecolor(row_line_color)
            cell.set_linewidth(0.8)

    table_img_name = f'{ticker}_yearly_stats.png'
    plt.savefig(table_img_name, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return table_img_name


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main():
    matplotlib.rc('font', family='AppleGothic')
    matplotlib.rcParams['axes.unicode_minus'] = False

    ticker = input('티커를 입력하세요 (예: SPY, QQQ, NVDA): ').strip().upper()
    if not ticker:
        ticker = 'NVDA'

    print(f'\n{ticker} 데이터 수집 중...')
    raw = yf.download(ticker, period='max', auto_adjust=True, progress=False)

    if raw.empty:
        print('데이터가 없습니다.')
        return

    prices = raw['Close'].squeeze().dropna()
    start_date = prices.index[0].strftime('%Y-%m-%d')
    end_date = prices.index[-1].strftime('%Y-%m-%d')

    # ── 1. 전체 기간 MDD ───────────────────────
    total_mdd = calc_mdd(prices)
    print(f'\n[전체 기간] 상장 이후 MDD: {total_mdd:.2f}% ({start_date} ~ {end_date})')

    # ── 2. 연도별 MDD + TR 테이블 ──────────────
    stats = yearly_stats(prices)
    print(f'\n[연도별 MDD & Total Return]\n{stats.to_string()}')

    # ── 3. 캡처 스타일 표 이미지 저장 ───────────
    table_img = save_table_image(ticker, stats, start_date, end_date)
    print(f'\n📊 표 이미지 저장 완료: {table_img}')

    # ── 4. 일별 Drawdown 차트 저장 ──────────────
    dd_series = daily_drawdown(prices)
    avg_dd  = dd_series.mean()
    max_dd  = dd_series.min()

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.fill_between(dd_series.index, dd_series.values, 0,
                    color='#1976d2', alpha=0.25, label='일별 Drawdown')
    ax.plot(dd_series.index, dd_series.values,
            color='#1976d2', linewidth=0.8)
    ax.axhline(avg_dd, color='#ffa726', linestyle='--', linewidth=1.3,
               label=f'평균 Drawdown ({avg_dd:.2f}%)')
    ax.axhline(max_dd, color='#d32f2f', linestyle=':', linewidth=1.3,
               label=f'최대 낙폭 MDD ({max_dd:.2f}%)')

    ax.set_title(f'{ticker} — 일별 Drawdown (상장 이후: {start_date} ~ {end_date})', fontsize=15, weight='bold')
    ax.set_xlabel('날짜')
    ax.set_ylabel('Drawdown (%)')
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    ax.legend(fontsize=11)
    plt.tight_layout()

    chart_img = f'{ticker}_daily_mdd.png'
    plt.savefig(chart_img, dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'📈 차트 이미지 저장 완료: {chart_img}')
    print('\n모든 작업이 완료되었습니다!')


if __name__ == '__main__':
    main()