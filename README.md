# 주식 및 지수 일일 모니터링 (Stock & Index Daily Monitoring)

이 프로젝트는 야후 파이낸스(yfinance) 데이터를 활용하여 주요 주식, 지수, 원자재 등의 일일 시세, 변동률, MDD(최대 낙폭), RSI 등을 분석하고, 정리된 표를 이미지로 생성하여 이메일로 전송하는 자동화 도구입니다.

## 주요 기능
- **주요 지수/종목 모니터링**: S&P500, NASDAQ, 채권, 금, 빅테크, 배당주 등 다양한 카테고리 지원
- **데이터 분석**:
  - 현재가, 전일 대비 변동률
  - RSI (14일 기준 과매수/과매도)
  - 이동평균선 (20일, 60일)
  - MDD (현재 고점 대비 하락률) 및 평균 MDD
  - **연초 대비 수익률 (YTD)** (새해 첫날에도 전년도 종가 기준으로 정확히 계산)
- **이미지 생성**: `matplotlib`을 사용하여 깔끔한 테이블 형태의 이미지(*.png) 생성
- **이메일 알림**: 생성된 이미지를 Gmail SMTP를 통해 자동 발송
- **자동화**: GitHub Actions를 통해 매일 특정 시간에 자동 실행 가능

## 설치 및 실행 방법

### 1. 환경 설정
Python 3.9 이상이 필요합니다.

```bash
# 가상환경 생성 (선택사항)
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

# 필수 라이브러리 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정
프로젝트 루트 경로에 `.env` 파일을 생성하고 아래 내용을 입력하세요. (Gmail 앱 비밀번호 필요)

```ini
SENDER_EMAIL=your_email@gmail.com
APP_PASSWORD=your_app_password
RECEIVER_EMAIL=recipient_email@gmail.com
```

### 3. 실행

**지수/ETF 모니터링 실행:**
```bash
python monitor_index.py
```
- 결과물: `index_monitoring_instagram.png`

**개별 종목/관심 종목 모니터링 실행:**
```bash
python monitor_stock.py
```
- 결과물: `stock_monitoring_instagram.png`

## 파일 설명
- `monitor_index.py`: 지수, 채권, 금 등 ETF 위주의 큰 흐름을 모니터링합니다.
- `monitor_stock.py`: 빅테크, 배당주, 주요 개별 종목을 상세하게 모니터링합니다.
- `calc_mdd.py`: MDD 계산 로직을 테스트하거나 확인하는 유틸리티입니다.
- `.github/workflows/monitor_stock.yml`: GitHub Actions 자동화 스크립트입니다.

## 주의사항
- `monitor_index.py`와 `monitor_stock.py`는 실행 시 `yfinance`를 통해 대량의 데이터를 가져오므로, 네트워크 환경에 따라 시간이 소요될 수 있습니다.
- Mac 환경에서는 한글 폰트(`AppleGothic`)가 기본 설정되어 있으며, Linux(GitHub Actions) 환경에서는 `NanumGothic`을 사용하도록 설정되어 있습니다.
