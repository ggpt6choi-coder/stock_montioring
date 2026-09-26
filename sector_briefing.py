"""
미국 S&P 500 11개 섹터 ETF 이평선 브리핑 - 텔레그램 자동 전송
"""

import os
import sys
import logging
import unicodedata
from datetime import datetime, date, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
import requests
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter 설정
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# 무료 모델 우선순위 (순서대로 fallback)
OPENROUTER_MODELS = [
    "qwen/qwen3.8-27b:free",                  # 한국어 강점, 무료
    "nvidia/nemotron-3-ultra-550b-a55b:free",  # 대형 무료 모델
    "google/gemma-4-31b-it:free",              # Google 무료
    "openai/gpt-4o",                           # 유료 최종 fallback
]

# 11개 섹터 ETF (티커: 한글 섹터명)
SECTOR_ETFS: dict[str, str] = {
    "XLK":  "기술",
    "XLC":  "통신",
    "XLY":  "임의소비재",
    "XLP":  "필수소비재",
    "XLV":  "헬스케어",
    "XLF":  "금융",
    "XLI":  "산업재",
    "XLE":  "에너지",
    "XLU":  "유틸리티",
    "XLRE": "부동산",
    "XLB":  "소재",
}

# 모바일 슬림 테이블용 2글자 약어
SECTOR_SHORT: dict[str, str] = {
    "XLK":  "기술",
    "XLC":  "통신",
    "XLY":  "소비",
    "XLP":  "필수",
    "XLV":  "헬스",
    "XLF":  "금융",
    "XLI":  "산업",
    "XLE":  "에너",
    "XLU":  "유틸",
    "XLRE": "부동",
    "XLB":  "소재",
}

# SMA 기간
MA_PERIODS = [20, 50, 200]

# 데이터 조회 기간 (200일 MA 계산에 충분한 여유)
DATA_PERIOD = "1y"

# ─────────────────────────────────────────────
# 데이터 수집 및 계산
# ─────────────────────────────────────────────

def fetch_closes(tickers: list[str], period: str = DATA_PERIOD) -> pd.DataFrame:
    """yfinance로 복수 티커 일봉 종가 수집."""
    logger.info(f"yfinance에서 {len(tickers)}개 티커 데이터 수집 중...")
    try:
        raw = yf.download(
            tickers,
            period=period,
            auto_adjust=True,
            progress=False,
        )
    except Exception as e:
        raise RuntimeError(f"yfinance 다운로드 실패: {e}") from e

    if raw.empty:
        raise ValueError("수신된 데이터가 없습니다. 장이 휴장 중이거나 네트워크 문제일 수 있습니다.")

    # Close 컬럼 추출 (단일/복수 티커 모두 처리)
    if isinstance(raw.columns, pd.MultiIndex):
        closes = raw["Close"]
    else:
        closes = raw[["Close"]].rename(columns={"Close": tickers[0]})

    closes = closes.dropna(how="all")
    logger.info(f"데이터 수집 완료 | 행: {len(closes)} | 마지막 날짜: {closes.index[-1].date()}")
    return closes


def compute_stats(closes: pd.DataFrame) -> list[dict]:
    """각 섹터 ETF의 SMA, 이격률, 배열 상태 계산."""
    results = []

    for ticker in SECTOR_ETFS:
        if ticker not in closes.columns:
            logger.warning(f"{ticker} 데이터 없음 — 건너뜀")
            continue

        series = closes[ticker].dropna()

        if len(series) < max(MA_PERIODS):
            logger.warning(f"{ticker} 데이터 부족({len(series)}행) — 건너뜀")
            continue

        last_close = series.iloc[-1]
        ma20  = series.rolling(20).mean().iloc[-1]
        ma50  = series.rolling(50).mean().iloc[-1]
        ma200 = series.rolling(200).mean().iloc[-1]

        def gap(price: float, ma: float) -> float:
            """이격률 (%)"""
            return ((price - ma) / ma) * 100

        gap20  = gap(last_close, ma20)
        gap50  = gap(last_close, ma50)
        gap200 = gap(last_close, ma200)

        # 배열 상태 판정
        if last_close > ma20 > ma50 > ma200:
            alignment = "정배열"
        elif last_close < ma20 < ma50 < ma200:
            alignment = "역배열"
        else:
            alignment = "혼조"

        results.append({
            "ticker":    ticker,
            "sector":    SECTOR_ETFS[ticker],
            "close":     last_close,
            "ma20":      ma20,
            "ma50":      ma50,
            "ma200":     ma200,
            "gap20":     gap20,
            "gap50":     gap50,
            "gap200":    gap200,
            "alignment": alignment,
        })

    return results


def is_market_holiday(last_date: date) -> bool:
    """마지막 데이터 날짜가 어제 또는 오늘보다 2일 이상 오래되었으면 휴장으로 판단."""
    today = date.today()
    delta = (today - last_date).days
    # 주말 포함 3일 이상 오래된 데이터면 경고
    return delta > 3


# ─────────────────────────────────────────────
# AI 코멘트 생성 (OpenRouter)
# ─────────────────────────────────────────────

def build_ai_prompt(stats: list[dict], ref_date: date) -> str:
    """AI에게 전달할 섹터 데이터 프롬프트 구성."""
    date_str = ref_date.strftime("%Y-%m-%d")

    lines = [f"기준일: {date_str}", ""]
    lines.append("섹터별 이평선 이격률 및 배열 상태:")
    for s in stats:
        lines.append(
            f"  {s['ticker']}({s['sector']}): "
            f"20일이격률={s['gap20']:+.1f}%, "
            f"50일이격률={s['gap50']:+.1f}%, "
            f"200일이격률={s['gap200']:+.1f}%, "
            f"배열={s['alignment']}"
        )

    above_200 = sum(1 for s in stats if s["gap200"] >= 0)
    sorted_gap20 = sorted(stats, key=lambda x: x["gap20"], reverse=True)
    lines.append(f"\n200일선 상회 섹터: {above_200} / {len(stats)}개")
    lines.append(f"20일선 이격률 1위: {sorted_gap20[0]['ticker']}({sorted_gap20[0]['sector']}) {sorted_gap20[0]['gap20']:+.1f}%")
    lines.append(f"20일선 이격률 최하: {sorted_gap20[-1]['ticker']}({sorted_gap20[-1]['sector']}) {sorted_gap20[-1]['gap20']:+.1f}%")

    data_summary = "\n".join(lines)

    return (
        f"[언어 규칙] 반드시 한국어로만 답변하세요. English is strictly prohibited.\n\n"
        f"당신은 미국 주식 섹터 로테이션 전문 애널리스트입니다.\n"
        f"아래 S&P 500 11개 섹터 ETF의 이동평균선 데이터를 분석하여\n"
        f"오늘의 시장 흐름을 아래 형식으로 정확히 4~5개 불릿 포인트로 작성해주세요.\n\n"
        f"[출력 형식 규칙 — 반드시 준수]\n"
        f"• 각 항목은 '• '으로 시작하는 한 줄\n"
        f"• 각 줄은 30자 이내로 간결하게\n"
        f"• 숫자/티커를 반드시 포함해 구체적으로\n"
        f"• 문단/이어지는 문장 금지 — 오직 불릿 라인만\n"
        f"• 투자 권유·매수·매도 추천 절대 금지\n\n"
        f"[분석 포인트]\n"
        f"• 자금이 몰리는 섹터 vs 이탈하는 섹터\n"
        f"• Risk-on / Risk-off 판단 (방어 vs 성장 섹터 흐름)\n"
        f"• 정배열/역배열 섹터 현황\n"
        f"• 200일선 기준 대세 추세\n"
        f"• 주목할 이상 신호 (있을 경우)\n\n"
        f"[예시 출력]\n"
        f"• XLK(기술) 20일선 +4.3%, 정배열 — 단기 강세 주도\n"
        f"• XLU(유틸리티) 역배열, 방어주 이탈 — Risk-on 흐름\n"
        f"• 200일선 상회 4/11개 — 대세 하락 압력 우세\n"
        f"• XLE 200일선 +11.9%에도 20일선 -2.6% — 단기 조정\n"
        f"• 정배열 섹터 XLK·XLV 외 대부분 혼조\n\n"
        f"[데이터]\n{data_summary}"
    )


def get_ai_comment(stats: list, ref_date: date) -> Optional[str]:
    """OpenRouter API로 AI 시황 코멘트 생성. 실패 시 None 반환."""
    if not OPENROUTER_API_KEY:
        logger.info("OPENROUTER_API_KEY 미설정 — AI 코멘트 건너뜀")
        return None

    prompt = build_ai_prompt(stats, ref_date)
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/stock-monitor",  # OpenRouter 정책용
        "X-Title": "Sector ETF Briefing",
    }

    for model in OPENROUTER_MODELS:
        try:
            logger.info(f"AI 코멘트 요청 중 (모델: {model})...")
            resp = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a professional Korean stock market analyst. "
                                "STRICT RULES:\n"
                                "1. Output ONLY 3-4 bullet points in Korean starting with '• '.\n"
                                "2. NEVER output your thinking process, explanation, or English text.\n"
                                "3. Do not include markdown headers (#) or introductions.\n"
                                "4. Output strictly starts with '• '."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 400,
                    "temperature": 0.4,  # 낮게 설정해 일관성 있는 분석 유도
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            comment = data["choices"][0]["message"]["content"].strip()
            logger.info(f"AI 코멘트 생성 완료 (모델: {model})")
            return comment

        except requests.exceptions.HTTPError as e:
            status = resp.status_code
            logger.warning(f"모델 {model} HTTP {status} 오류: {e} — 다음 모델 시도")
            if status == 429:  # Rate limit — 다음 모델로
                continue
            if status in (402, 403):  # 크레딧 부족 — 다음 모델로
                continue
            break  # 다른 에러는 즉시 중단
        except requests.exceptions.Timeout:
            logger.warning(f"모델 {model} 타임아웃 — 다음 모델 시도")
            continue
        except Exception as e:
            logger.warning(f"모델 {model} 예외: {e} — AI 코멘트 생략")
            break

    logger.warning("모든 AI 모델 실패 — AI 코멘트 없이 진행")
    return None


# ─────────────────────────────────────────────
# 시각 폭 효리티 (CJK·이모지 = 2칸)
# ─────────────────────────────────────────────

def _vlen(s: str) -> int:
    """시각적 열 폭 계산 (CJK 한글·이모지 = 2커, ASCII = 1커)."""
    total = 0
    for ch in s:
        cp = ord(ch)
        # 이모지 범위 (unicodedata가 narrow로 잘못 신고하는 고립령 비트맵맵 색상 원 등)
        if (
            0x1F300 <= cp <= 0x1FAFF  # 미스셀러니얰스 기호 / 확장
            or 0x2600  <= cp <= 0x27BF  # 다양한 기호 (Clock 등)
            or 0x1F000 <= cp <= 0x1F02F # 마작패 타일 등
        ):
            total += 2
        else:
            eaw = unicodedata.east_asian_width(ch)
            total += 2 if eaw in ('W', 'F') else 1
    return total


def _vpad(s: str, width: int, align: str = '<') -> str:
    """시각 폭 기준 정렬. align: '<' 좌, '>' 우, '^' 중앙."""
    pad = max(0, width - _vlen(s))
    if align == '<':
        return s + ' ' * pad
    elif align == '>':
        return ' ' * pad + s
    else:  # center
        left = pad // 2
        return ' ' * left + s + ' ' * (pad - left)


# ─────────────────────────────────────────────
# 메시지 포맷팅 (모바일 초슬림 규격: 30자 이내)
# ─────────────────────────────────────────────

def fmt_slim_gap(gap: float, width: int = 4) -> str:
    """모바일용 슬림 수치 포맷팅: +4.3 or -1.9 or +20%"""
    if abs(gap) >= 9.95:
        # 두 자리 수 이상이면 정수%로 표기하여 자릿수 절약
        s = f"{gap:+3.0f}%"
    else:
        s = f"{gap:+4.1f}"
    return _vpad(s, width, ">")


def clean_ai_comment(raw_text: Optional[str], stats: list) -> str:
    """
    AI 응답에서 생각 과정(Thinking), 영어 문장을 완전히 제거하고
    깨끗한 한국어 불릿 포인트만 추출합니다. 실패 시 룰베이스 퀀트 요약으로 대체.
    """
    import re
    import html as _html

    if raw_text:
        # 1. <think> 태그 제거
        text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL)
        
        valid_bullets = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # 영어 생각/메타 문장 제거
            lower = line.lower()
            if any(p in lower for p in [
                'the user wants', 'let me analyze', 'here is', 'here are',
                'based on the data', 'in korean', 'strict format', 'bullet point'
            ]):
                continue
            
            # 불릿 기호 정규화
            clean_line = re.sub(r'^[\-\*•\d\.\s]+', '• ', line)
            
            # 한글이 최소 3글자 이상 포함되어 있는지 확인
            korean_chars = re.findall(r'[가-힣]', clean_line)
            if len(korean_chars) >= 3 and clean_line.startswith('• '):
                valid_bullets.append(_html.escape(clean_line))

        if len(valid_bullets) >= 2:
            return "\n".join(valid_bullets[:4])

    # ── Fallback: 룰베이스 퀀트 자동 요약 ──
    above_200 = sum(1 for s in stats if s["gap200"] >= 0)
    sorted_by_gap20 = sorted(stats, key=lambda x: x["gap20"], reverse=True)
    bullish = [s['ticker'] for s in stats if s['alignment'] == '정배열']
    bearish = [s['ticker'] for s in stats if s['alignment'] == '역배열']

    bullets = [
        f"• 200일선 상회 {above_200}/11개 — {'대세 상승 국면 유지' if above_200 >= 8 else '단기 하락 및 조정 압력 우세'}",
        f"• 단기 주도 섹터: {sorted_by_gap20[0]['ticker']}({sorted_by_gap20[0]['sector']}) {sorted_by_gap20[0]['gap20']:+.1f}% 강세",
        f"• 단기 조정 섹터: {sorted_by_gap20[-1]['ticker']}({sorted_by_gap20[-1]['sector']}) {sorted_by_gap20[-1]['gap20']:+.1f}% 약세",
    ]
    if bullish:
        bullets.append(f"• 정배열 추세 섹터: {', '.join(bullish)}")
    elif bearish:
        bullets.append(f"• 역배열 경계 섹터: {', '.join(bearish)}")

    return "\n".join(bullets)


def build_message(stats: list, ref_date: date, ai_comment: Optional[str] = None) -> str:
    """텔레그램 HTML 메시지 생성 (모바일 한 줄 30자 슬림 규격)."""
    date_str = ref_date.strftime("%Y-%m-%d")

    # ── 헤더 ──────────────────────────────────
    header = (
        f"📊 <b>미국 증시 11개 섹터 이평선 브리핑</b>\n"
        f"(기준: {date_str} 장마감)\n\n"
    )

    # ── 모바일 슬림 테이블 (총 30칸으로 모바일 줄바꿈 100% 방지) ────
    # 컬럼 구성: 티커(4) 섹터(4) 20(4) 50(4) 200(5) 상태(4) + 공백 5 = 30칸
    hdr = (
        f"{_vpad('티커', 4)} "
        f"{_vpad('섹터', 4)} "
        f"{_vpad('20', 4, '>')} "
        f"{_vpad('50', 4, '>')} "
        f"{_vpad('200', 5, '>')} "
        f"상태"
    )
    divider = "-" * 30  # 시각폭 30칸과 정확히 일치

    rows = [hdr, divider]
    for s in stats:
        tk_short = SECTOR_SHORT.get(s["ticker"], s["sector"][:2])
        g20  = fmt_slim_gap(s["gap20"], 4)
        g50  = fmt_slim_gap(s["gap50"], 4)
        g200 = fmt_slim_gap(s["gap200"], 5)

        # 상태 이모지 및 약어 (🟢정, 🟡혼, 🔴역)
        if s["alignment"] == "정배열":
            status = "🟢정"
        elif s["alignment"] == "역배열":
            status = "🔴역"
        else:
            status = "🟡혼"

        row = (
            f"{_vpad(s['ticker'], 4)} "
            f"{_vpad(tk_short, 4)} "
            f"{g20} "
            f"{g50} "
            f"{g200} "
            f"{status}"
        )
        rows.append(row)

    table = "<pre>" + "\n".join(rows) + "</pre>\n"

    # ── 시장 건전성 요약 ──────────────────────
    above_200 = sum(1 for s in stats if s["gap200"] >= 0)
    total = len(stats)

    sorted_by_gap20 = sorted(stats, key=lambda x: x["gap20"], reverse=True)
    top2    = ", ".join(f"{s['ticker']}({s['sector']})" for s in sorted_by_gap20[:2])
    bottom2 = ", ".join(f"{s['ticker']}({s['sector']})" for s in sorted_by_gap20[-2:])

    if above_200 >= 8:
        trend_comment = "대세 상승 추세 유지"
    elif above_200 >= 5:
        trend_comment = "혼조 — 방향성 탐색 중"
    else:
        trend_comment = "대세 하락 압력"

    summary = (
        f"📌 <b>시장 건전성 요약</b>\n"
        f"• 200일선 상회: <b>{above_200} / {total}개</b> ({trend_comment})\n"
        f"• 단기 주도 섹터(20일선 상위): <b>{top2}</b>\n"
        f"• 단기 조정 섹터(20일선 하위): <b>{bottom2}</b>"
    )

    # ── AI 시황 코멘트 (클린 필터링 적용) ──────
    cleaned_comment = clean_ai_comment(ai_comment, stats)
    ai_block = (
        f"\n\n🤖 <b>AI 시황 코멘트</b>\n"
        f"{cleaned_comment}"
    )

    legend = "\n\n<pre>* 상태: 🟢정(정배열) 🟡혼(혼조) 🔴역(역배열)</pre>"

    return header + table + summary + ai_block + legend


# ─────────────────────────────────────────────
# 텔레그램 전송
# ─────────────────────────────────────────────

def send_telegram(message: str, bot_token: str, chat_id: str) -> None:
    """텔레그램 Bot API로 HTML 메시지 전송."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("텔레그램 메시지 전송 성공!")
    except requests.exceptions.HTTPError as e:
        logger.error(f"텔레그램 HTTP 오류: {e} | 응답: {resp.text}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"텔레그램 네트워크 오류: {e}")
        raise


def send_error_notification(bot_token: str, chat_id: str, error_msg: str) -> None:
    """오류 발생 시 텔레그램으로 에러 알림 전송."""
    msg = (
        "⚠️ <b>섹터 이평선 브리핑 실행 오류</b>\n\n"
        f"<code>{error_msg}</code>"
    )
    try:
        send_telegram(msg, bot_token, chat_id)
    except Exception:
        logger.exception("에러 알림 전송도 실패")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main() -> None:
    # 환경변수 검증
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error(
            "TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다.\n"
            ".env 파일 또는 GitHub Secrets를 확인해주세요."
        )
        sys.exit(1)

    tickers = list(SECTOR_ETFS.keys())

    try:
        # 1. 데이터 수집
        closes = fetch_closes(tickers)

        # 2. 마지막 거래일 확인
        last_date: date = closes.index[-1].date()
        if is_market_holiday(last_date):
            logger.warning(
                f"마지막 데이터 날짜({last_date})가 오래되었습니다. "
                "주말/공휴일 직후이거나 데이터 지연일 수 있습니다."
            )

        # 3. 통계 계산
        stats = compute_stats(closes)

        if not stats:
            raise ValueError("유효한 섹터 데이터가 없습니다.")

        logger.info(f"계산 완료 | 총 {len(stats)}개 섹터")

        # 4. AI 코멘트 생성 (API 키 없거나 실패해도 계속 진행)
        ai_comment = get_ai_comment(stats, last_date)

        # 5. 메시지 생성
        message = build_message(stats, last_date, ai_comment)
        logger.info("메시지 생성 완료")
        logger.debug(f"\n{message}")

        # 6. 텔레그램 전송
        send_telegram(message, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

    except Exception as e:
        logger.exception(f"예상치 못한 오류 발생: {e}")
        # 텔레그램으로 에러 알림 전송 (토큰이 있는 경우에만)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            send_error_notification(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
