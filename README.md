# 📈 미국 주식 퀀트 모니터링 & 자동화 시스템 (Stock Monitor)

미국 증시 및 주요 ETF/개별 종목의 데이터를 매일 자동으로 수집·분석하고, **텔레그램 알림**, **이메일 리포트**, **고화질 분석 이미지**로 발행하는 올인원 퀀트 자동화 툴킷입니다.

---

## 📑 목차
1. [핵심 기능 한눈에 보기](#-핵심-기능-한눈에-보기)
2. [기능별 상세 사용설명서](#-기능별-상세-사용설명서)
   - [1. 섹터 ETF 이평선 & AI 브리핑 (`sector_briefing.py`)](#1-섹터-etf-이평선--ai-브리핑-sector_briefingpy)
   - [2. 역사적 MDD & 연간 수익률(TR) 시각화 (`calc_mdd.py`)](#2-역사적-mdd--연간-수익률tr-시각화-calc_mddpy)
   - [3. 데일리 주식/지수 종합 리포트 (`monitor_stock.py`)](#3-데일리-주식지수-종합-리포트-monitor_stockpy)
   - [4. 무한매수법 백테스트 시뮬레이터 (`simul_limit_strategy.py`)](#4-무한매수법-백테스트-시뮬레이터-simul_limit_strategypy)
3. [설치 및 환경 설정](#-설치-및-환경-설정)
4. [GitHub Actions 자동화 & 영구 유지 관리](#-github-actions-자동화--영구-유지-관리)
5. [프로젝트 파일 구조](#-프로젝트-파일-구조)

---

## 🚀 핵심 기능 한눈에 보기

| 스크립트 | 실행 목적 | 주요 산출물 / 알림 | 자동화 스케줄 |
| :--- | :--- | :--- | :--- |
| **`sector_briefing.py`** | S&P 500 11개 섹터 ETF 이평선 괴리율 및 AI 시장 건전성 진단 | 텔레그램 메시지 발송 | 매일 06:30 (KST, 화~토) |
| **`calc_mdd.py`** | 전 종목 역사적 연도별 MDD 및 Total Return(TR) 계산 | `{TICKER}_yearly_stats.png` (고화질 표)<br>`{TICKER}_daily_mdd.png` (차트) | 온디맨드 (수시 실행) |
| **`monitor_stock.py`** | 빅테크, 지수, 채권, 공포/탐욕 지수, Finviz 맵 종합 모니터링 | `stock_monitoring_instagram.png`<br>이메일(Gmail) & 텔레그램 발송 | 매일 07:00 (KST) |
| **`simul_limit_strategy.py`** | 라오어 무한매수법(40회 분할 매수) 백테스트 | `result/*.csv` 시뮬레이션 결과 | 온디맨드 (수시 실행) |

---

## 📖 기능별 상세 사용설명서

### 1. 섹터 ETF 이평선 & AI 브리핑 (`sector_briefing.py`)

미국 S&P 500의 11개 섹터 ETF(XLK, XLC, XLY 등)의 **20일, 50일, 200일 단순이동평균(SMA)**과 현재 주가 간 괴리율을 계산하고, **OpenRouter AI(Qwen/Nemotron/GPT-4o)**가 시장 건전성을 3줄로 요약하여 텔레그램으로 전송합니다.

* **실행 명령어:**
  ```bash
  source venv/bin/activate
  python sector_briefing.py
  ```
* **특징:**
  * 동아시아 전각 문자 시각폭 정렬 알고리즘 적용으로 모바일 텔레그램에서도 열이 칼같이 정렬됨
  * 상회 시 🟢, 하회 시 🔴 이모지로 직관적 식별
  * 이평선 배열 상태(정배열, 역배열, 혼조) 자동 판정
  * AI가 불릿 포인트(•)로 시장 주도 섹터 및 방어주 쏠림 여부를 객관적 진단

---

### 2. 역사적 MDD & 연간 수익률(TR) 시각화 (`calc_mdd.py`)

지수(SPY, QQQ), 레버리지(TQQQ, QLD), 개별 주식(NVDA, TSLA), 국내 주식(005930.KS) 등 **전 세계 모든 종목의 상장 첫날부터 현재까지의 연도별 최대 낙폭(MDD)과 연간 총수익률(TR)**을 산출합니다.

* **실행 명령어:**
  ```bash
  source venv/bin/activate
  python calc_mdd.py
  ```
  실행 후 콘솔창에 분석할 티커(예: `SPY`, `NVDA`, `QQQ`)를 입력하고 엔터를 누릅니다.
* **산출물:**
  1. **콘솔 테이블:** 연도별 MDD, TR, 전체 평균치 출력
  2. **`{TICKER}_yearly_stats.png`**: 투자 서적 디자인과 동일한 깔끔한 카드형 표(Table) 고해상도 이미지
  3. **`{TICKER}_daily_mdd.png`**: 일별 Drawdown 낙폭 시계열 그래프
* **계산 공식 원리:**
  * **MDD (Max Drawdown):** 연중 매 거래일의 누적 최고점(`cummax`) 대비 일별 낙폭(`drawdown`) 중 최악의 순간(`min()`)을 추적 (연말 반등에 따른 왜곡을 원천 차단하는 정석 퀀트 공식)
  * **Total Return (TR):** 수정주가(`auto_adjust=True`) 기반으로 배당 및 주식분할이 모두 반영된 연간 실질 총수익률

---

### 3. 데일리 주식/지수 종합 리포트 (`monitor_stock.py`)

주요 빅테크 및 관심 종목의 일일 시세, 변동률, RSI(14), 연초 대비 수익률(YTD), MDD를 집계하고, 시장 심리(Fear & Greed)와 Finviz 시장 지도(Heatmap)를 결합하여 인스타그램 1:1 규격 이미지로 생성 후 알림을 발송합니다.

* **실행 명령어:**
  ```bash
  source venv/bin/activate
  python monitor_stock.py
  ```
* **산출물:**
  * `stock_monitoring_instagram.png` (종합 테이블 이미지)
  * `index_monitoring_instagram.png` (지수/ETF 테이블 이미지)
  * `sentiment_monitoring.png` (공포/탐욕 지수 이미지)
  * `market_map.png` (Finviz 시장 맵 캡처)
  * Gmail 및 텔레그램으로 이미지 일괄 전송

---

### 4. 무한매수법 백테스트 시뮬레이터 (`simul_limit_strategy.py`)

미국 레버리지 ETF(TQQQ 등)를 대상으로 40회 분할 매수 및 수익률 달성 시 매도하는 라오어 무한매수법 알고리즘 백테스트 엔진입니다.

* **실행 명령어:**
  ```bash
  source venv/bin/activate
  python simul_limit_strategy.py
  ```
* **모드 설정 (`simul_limit_strategy.py` 상단):**
  * `MODE = "SEQUENTIAL"`: 실제 투자처럼 한 사이클이 끝나면 다음 사이클로 자본을 넘겨 총 자산 변화를 추적
  * `MODE = "ROLLING"`: 기간 내 매일 새로운 40일 사이클을 개시하여 전략의 평균 승률 및 기간별 통계 도출
* **결과 저장:** `result/` 폴더 내에 일자별 세부 매매 기록 CSV 파일로 자동 저장

---

## 🛠️ 설치 및 환경 설정

### 1. 가상환경 구성 및 의존성 설치
```bash
python3 -m venv venv
source venv/bin/activate

# 필수 패키지 설치
pip install -r requirements.txt
pip install "yfinance>=0.2.50" "pandas>=2.0.0" requests python-dotenv

# 헤드리스 브라우저 의존성 (Finviz 캡처용)
python -m playwright install chromium
```

### 2. 환경변수(`.env`) 설정
`.env.example`을 복사하여 `.env`를 생성하고 실제 키 값을 입력합니다.

```bash
cp .env.example .env
```

```ini
# 텔레그램 알림용 (sector_briefing.py, monitor_stock.py)
TELEGRAM_BOT_TOKEN=8448204047:AAGiv40MLojvOFO8MVC_D_PfYhEKN3QhCBQ
TELEGRAM_CHAT_ID=-1003949523996

# AI 시장 요약 코멘트용 (sector_briefing.py)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 이메일 발송용 (monitor_stock.py)
SENDER_EMAIL=your_email@gmail.com
APP_PASSWORD=your_gmail_app_password
RECEIVER_EMAIL=recipient_email@gmail.com
```

---

## ⚙️ GitHub Actions 자동화 & 영구 유지 관리

GitHub 클라우드에서 컴퓨터를 켜두지 않아도 100% 무료로 매일 정해진 시간에 자동 실행됩니다.

### 1. 워크플로우 종류
* **`.github/workflows/daily_briefing.yml`**: 미국 장마감 직후인 한국시간 **화~토 06:30**에 섹터 이평선 브리핑 실행
* **`.github/workflows/monitor_stock.yml`**: 매일 한국시간 **07:00**에 종합 종목 리포트 생성 및 전송
* **`.github/workflows/keepalive.yml`**: **60일 비활성화 영구 방지 봇** (매월 1일, 15일 자동 실행)

### 2. GitHub Secrets 등록
GitHub 저장소 ➔ **Settings** ➔ **Secrets and variables** ➔ **Actions**에 아래 변수를 등록합니다:
* `TELEGRAM_BOT_TOKEN`
* `TELEGRAM_CHAT_ID`
* `OPENROUTER_API_KEY`
* `SENDER_EMAIL`, `APP_PASSWORD`, `RECEIVER_EMAIL` (이메일 사용 시)

### 3. 60일 자동 비활성화 방지 설정 (필수 1회)
GitHub는 60일간 커밋이 없으면 스케줄러를 자동 정지시킵니다. 이를 방지하기 위해 생성된 `keepalive.yml`이 정상 작동하도록 권한을 열어주세요:
1. 저장소 **Settings** ➔ 좌측 **Actions** ➔ **General** 클릭
2. 맨 아래 **Workflow permissions**에서 **`Read and write permissions`** 선택 후 **Save**

---

## 📁 프로젝트 파일 구조

```text
stock-monitor/
├── .github/workflows/
│   ├── daily_briefing.yml     # 섹터 이평선 텔레그램 브리핑 워크플로우
│   ├── monitor_stock.yml      # 데일리 종합 리포트 워크플로우
│   └── keepalive.yml          # Actions 60일 비활성화 방지 워크플로우
├── .env                       # 로컬 환경변수 (비공개 토큰)
├── .env.example               # 환경변수 템플릿
├── calc_mdd.py                # MDD & Total Return 계산 및 표/차트 이미지 생성기
├── sector_briefing.py         # 11개 섹터 ETF 이평선 분석 및 AI 시장 브리핑
├── monitor_stock.py           # 개별 종목 데일리 모니터링 메인 스크립트
├── monitor_index.py           # 지수/채권/원자재 모니터링 보조 스크립트
├── monitor_sentiment.py       # Fear & Greed 공포/탐욕 지수 생성 모듈
├── monitor_map.py             # Finviz 시장 맵 캡처 모듈
├── notifier.py                # 이메일/텔레그램 통합 알림 발송 모듈
├── simul_limit_strategy.py    # 라오어 무한매수법 백테스트 시뮬레이터
├── requirements.txt           # 파이썬 의존성 목록
└── README.md                  # 프로젝트 사용설명서
```
