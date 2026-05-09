import yfinance as yf
import pandas as pd
import numpy as np
from datetime import timedelta
import os

# ==========================================
# [설정] 억만장자 전문가의 시뮬레이션 세팅
# ==========================================
TICKER = "TQQQ"
START_DATE = "2022-01-01"  # 시뮬레이션 시작일
END_DATE = "2022-12-31"    # 시뮬레이션 종료일
TOTAL_SEED = 10000         # 총 자본금 (SEQUENTIAL 모드용)

# 시뮬레이션 모드 설정:
# "SEQUENTIAL" -> 실제 매매처럼 한 사이클이 끝나면 다음 사이클 시작 (자산 변화 추적)
# "ROLLING"    -> 기간 내 모든 거래일마다 각각 40일 사이클을 시작하여 통계 도출
# MODE = "ROLLING" 
MODE = "SEQUENTIAL" 
# ==========================================

def get_prepared_data(ticker, start, end):
    # 충분한 데이터를 가져오기 위해 앞쪽으로 버퍼를 둠
    fetch_start = pd.to_datetime(start) - timedelta(days=50)
    # ROLLING 모드에서 마지막 날짜가 40일을 채울 수 있도록 뒤쪽으로도 버퍼를 둠
    fetch_end = pd.to_datetime(end) + timedelta(days=100)
    
    df = yf.download(ticker, start=fetch_start, end=fetch_end, progress=False)
    if df.empty: return None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df

def simulate_one_cycle(df, start_date, seed):
    """지정된 시작일로부터 하나의 무한매수법 사이클(최대 40일)을 수행"""
    # 시작일 이후의 데이터 필터링
    df_cycle = df[df.index >= start_date].head(60) # 넉넉하게 60일치 확보
    if df_cycle.empty: return None

    daily_budget = seed / 40
    cash = seed
    shares = 0
    invested_amount = 0
    avg_price = 0
    day_count = 0
    is_soul_mode = False

    for date, row in df_cycle.iterrows():
        price = row['Close']
        high = row['High']
        day_count += 1
        
        # [STEP 1] 매도 체크
        target_profit = 0.10
        if day_count > 30: target_profit = 0.03
        elif day_count > 20: target_profit = 0.07
        
        if shares > 0:
            target_sell_price = avg_price * (1 + target_profit)
            if high >= target_sell_price:
                profit = (shares * target_sell_price) - invested_amount
                return {
                    'Start': start_date.strftime('%Y-%m-%d'), 'End': date.strftime('%Y-%m-%d'), 
                    'Days': day_count, 'Profit': round(profit, 2), 
                    'Return': round(target_profit * 100, 2), 'Status': 'Success'
                }

        # [STEP 2] 매수 (최대 40일까지)
        if day_count <= 40:
            if day_count == 1:
                buy_shares = int(daily_budget // price)
            else:
                half = daily_budget / 2
                shares_b = int(half // price)
                shares_a = int(half // price) if price <= avg_price else 0
                buy_shares = shares_a + shares_b
            
            buy_cost = buy_shares * price
            shares += buy_shares
            invested_amount += buy_cost
            avg_price = invested_amount / shares if shares > 0 else 0
            
            # [HARD LIMIT] 40일이 되었는데도 매도가 안 되었다면 여기서 종료 (Rolling 통계용)
            if day_count == 40:
                current_profit = (shares * price) - invested_amount
                current_return = (shares * price / invested_amount - 1) * 100 if invested_amount > 0 else 0
                return {
                    'Start': start_date.strftime('%Y-%m-%d'), 'End': date.strftime('%Y-%m-%d'), 
                    'Days': day_count, 'Profit': round(current_profit, 2), 
                    'Return': round(current_return, 2), 'Status': 'Ended (40d)'
                }
        
        # Soul Mode 및 60일 가드는 ROLLING 모드(simulate_one_cycle)에서는 제거 (40일 하드 리밋에 통합)
    return None

def run_sequential(df, start, end, seed):
    """이전 코드와 동일한 방식의 연속 매매 시뮬레이션"""
    df_sim = df[(df.index >= start) & (df.index <= end)]
    
    cash = seed
    shares = 0
    invested_amount = 0
    avg_price = 0
    day_count = 0
    is_soul_mode = False
    
    history = []
    cycles = []
    current_cycle_start = df_sim.index[0]
    daily_budget = seed / 40

    for date, row in df_sim.iterrows():
        price = row['Close']
        high = row['High']
        day_count += 1
        
        target_profit = 0.10
        if day_count > 30: target_profit = 0.03
        elif day_count > 20: target_profit = 0.07
        
        is_sold = False
        if shares > 0:
            target_sell_price = avg_price * (1 + target_profit)
            if high >= target_sell_price:
                cash += shares * target_sell_price
                profit = (shares * target_sell_price) - invested_amount
                cycles.append({'Start': current_cycle_start.strftime('%Y-%m-%d'), 'End': date.strftime('%Y-%m-%d'), 'Days': day_count, 'Profit': round(profit, 2), 'Status': 'Success'})
                shares, invested_amount, avg_price, day_count = 0, 0, 0, 0
                is_soul_mode = False
                current_cycle_start = date + timedelta(days=1)
                is_sold = True

        if is_sold: continue

        if day_count <= 40 and not is_soul_mode:
            if day_count == 1: buy_shares = int(daily_budget // price)
            else:
                half = daily_budget / 2
                shares_b = int(half // price)
                shares_a = int(half // price) if price <= avg_price else 0
                buy_shares = shares_a + shares_b
            
            buy_cost = buy_shares * price
            if cash >= buy_cost:
                shares += buy_shares
                cash -= buy_cost
                invested_amount += buy_cost
                avg_price = invested_amount / shares if shares > 0 else 0
        
        elif day_count > 40 or is_soul_mode:
            is_soul_mode = True
            if high >= avg_price:
                sell_soul_shares = int(shares * 0.25)
                cash += sell_soul_shares * avg_price
                invested_amount -= sell_soul_shares * avg_price
                shares -= sell_soul_shares
                day_count, is_soul_mode = 1, False

        total_equity = cash + (shares * price)
        current_return = (shares * price / invested_amount - 1) * 100 if invested_amount > 0 else 0
        history.append({
            'Date': date.strftime('%Y-%m-%d'), 'Price': round(price, 2), 'AvgPrice': round(avg_price, 2),
            'Shares': shares, 'Invested': round(invested_amount, 2), 'Cash': round(cash, 2),
            'Total': round(total_equity, 2), 'Return(%)': round(current_return, 2), 'DayCount': day_count,
            'Mode': 'Soul' if is_soul_mode else 'Normal'
        })

    return pd.DataFrame(history), pd.DataFrame(cycles)

def run_rolling(df, start, end, seed):
    """모든 시작 가능일에 대해 40일 사이클을 독립적으로 수행"""
    df_range = df[(df.index >= start) & (df.index <= end)]
    results = []
    
    print(f"ROLLING 모드: {len(df_range)}개의 시작일에 대해 시뮬레이션 중...")
    
    for start_date in df_range.index:
        res = simulate_one_cycle(df, start_date, seed)
        if res:
            results.append(res)
            
    return pd.DataFrame(results)

# --- 메인 실행 로직 ---
raw_df = get_prepared_data(TICKER, START_DATE, END_DATE)

if raw_df is not None:
    output_dir = "result"
    os.makedirs(output_dir, exist_ok=True)

    if MODE == "SEQUENTIAL":
        history_df, cycles_df = run_sequential(raw_df, START_DATE, END_DATE, TOTAL_SEED)
        print(f"=== {TICKER} 무한매수법 V2.1 시뮬레이션 결과 (SEQUENTIAL) ===")
        print(f"최종 자산: ${history_df['Total'].iloc[-1]:,.2f}")
        print(f"총 수익률: {((history_df['Total'].iloc[-1] / TOTAL_SEED) - 1) * 100:.2f}%")
        print(f"총 사이클 횟수: {len(cycles_df)}회")
        
        csv_filename = os.path.join(output_dir, f"simul_sequential_{TICKER}_{START_DATE}_{END_DATE}.csv")
        with open(csv_filename, 'w', encoding='utf-8') as f:
            f.write(f"# [ 무한매수법 V2.1 시뮬레이션 요약 - SEQUENTIAL ]\n")
            f.write(f"# 종목: {TICKER} | 기간: {START_DATE} ~ {END_DATE}\n")
            f.write(f"# 최종 자산: ${history_df['Total'].iloc[-1]:,.2f} | 총 수익률: {((history_df['Total'].iloc[-1] / TOTAL_SEED) - 1) * 100:.2f}%\n\n")
        
        history_df.to_csv(csv_filename, mode='a', index=False)
        print(f"\n[알림] 상세 진행 과정이 '{csv_filename}'로 저장되었습니다.")
        print("\n--- 최근 15일 진행 상황 ---")
        print(history_df.tail(15).to_string(index=False))

    elif MODE == "ROLLING":
        results_df = run_rolling(raw_df, START_DATE, END_DATE, TOTAL_SEED)
        print(f"\n=== {TICKER} 무한매수법 V2.1 시뮬레이션 결과 (ROLLING) ===")
        print(f"총 테스트 건수: {len(results_df)}건")
        
        success_df = results_df[results_df['Status'] == 'Success']
        win_rate = (len(success_df) / len(results_df)) * 100 if len(results_df) > 0 else 0
        
        print(f"성공(익절) 횟수: {len(success_df)}회")
        print(f"승률: {win_rate:.2f}%")
        print(f"평균 수익률: {results_df['Return'].mean():.2f}%")
        print(f"평균 소요 기간: {results_df['Days'].mean():.1f}일")
        
        csv_filename = os.path.join(output_dir, f"simul_rolling_{TICKER}_{START_DATE}_{END_DATE}.csv")
        with open(csv_filename, 'w', encoding='utf-8') as f:
            f.write(f"# [ 무한매수법 V2.1 시뮬레이션 요약 - ROLLING ]\n")
            f.write(f"# 종목: {TICKER} | 기간: {START_DATE} ~ {END_DATE}\n")
            f.write(f"# 테스트 건수: {len(results_df)} | 승률: {win_rate:.2f}% | 평균 수익률: {results_df['Return'].mean():.2f}%\n\n")
            
        results_df.to_csv(csv_filename, mode='a', index=False)
        print(f"\n[알림] 모든 사이클 결과가 '{csv_filename}'로 저장되었습니다.")
        print("\n--- 최근 15개 사이클 결과 ---")
        print(results_df.tail(15).to_string(index=False))
else:
    print("데이터를 불러올 수 없습니다.")