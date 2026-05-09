import yfinance as yf
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.patches import Wedge, FancyBboxPatch, Circle
from datetime import datetime
import json
import platform
import matplotlib
import time
from notifier import notify

# ── 폰트 ──────────────────────────────────────────────────
system_name = platform.system()
if system_name == 'Darwin':
    matplotlib.rc('font', family='AppleGothic')
elif system_name == 'Linux':
    matplotlib.rc('font', family='NanumGothic')
matplotlib.rcParams['axes.unicode_minus'] = False

# ── 파스텔 팔레트 ──────────────────────────────────────────
BG      = '#F8F9FA'
CARD    = '#FFFFFF'
DIVIDER = '#E0E0E0'
TITLE   = '#000000'       # 제목: 완전 검정
TEXT    = '#000000'
SUBTEXT = '#666666'

# Fear & Greed 파스텔 5구간
FG_SEG  = ['#FFAAAA', '#FFCC99', '#FFE699', '#BBEEBB', '#99CC99']
FG_LBL  = ['극도공포\n(0-25)', '공포\n(26-45)', '중립\n(46-55)', '탐욕\n(56-75)', '극도탐욕\n(76-100)']
FG_RNG  = [(0,25),(25,45),(45,55),(55,75),(75,100)]

# VIX 파스텔 단계
VIX_SEG = ['#99CC99','#BBEEBB','#FFCC99','#FFAAAA']

RATING_KR = {'extreme fear':'극도의 공포','fear':'공포',
             'neutral':'중립','greed':'탐욕','extreme greed':'극도의 탐욕'}
def to_kr(r): return RATING_KR.get(str(r).lower(), r)

def fg_color(s):
    if s<=25: return '#FF8888'
    elif s<=45: return '#FFB366'
    elif s<=55: return '#FFD700'
    elif s<=75: return '#88CC88'
    else: return '#55AA55'

def vix_color(v):
    if v<=15: return '#55AA55'
    elif v<=25: return '#88CC88'
    elif v<=35: return '#FFB366'
    else: return '#FF8888'

def score_text_color(s):
    """점수에 따른 진한 텍스트 색상"""
    if s<=25: return '#CC2222'
    elif s<=45: return '#CC7700'
    elif s<=55: return '#AA8800'
    elif s<=75: return '#337733'
    else: return '#226622'

# ── 데이터 수집 ────────────────────────────────────────────
CACHE_FILE = 'fg_cache.json'

BROWSER_HEADERS = {
    'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection':      'keep-alive',
}

def _parse_fg_response(d):
    fg   = d['fear_and_greed']
    hist = d.get('fear_and_greed_historical', {}).get('data', [])
    prev = hist[-2] if len(hist) >= 2 else {}
    return {
        'score':      round(float(fg['score']), 1),
        'rating':     fg['rating'],
        'prev_score': round(float(prev.get('y', fg['score'])), 1),
        'prev_rating':prev.get('rating', fg['rating']),
        'cached':     False,
    }

def fetch_fear_and_greed(max_retries=3):
    api_url  = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    page_url = "https://edition.cnn.com/markets/fear-and-greed"

    for attempt in range(1, max_retries + 1):
        try:
            session = requests.Session()
            # ① 실제 브라우저처럼 CNN 페이지 먼저 방문 → 쿠키 획득
            session.get(page_url, headers=BROWSER_HEADERS, timeout=10)
            # ② 쿠키가 담긴 세션으로 API 호출
            api_headers = dict(BROWSER_HEADERS)
            api_headers.update({
                'Accept':  'application/json, text/plain, */*',
                'Referer': page_url,
                'Origin':  'https://edition.cnn.com',
            })
            r = session.get(api_url, headers=api_headers, timeout=10)
            if not r.text.strip():
                raise ValueError("빈 응답")
            result = _parse_fg_response(r.json())
            # 성공 시 캐시 저장
            with open(CACHE_FILE, 'w') as f:
                json.dump(result, f)
            print(f"Fear & Greed 조회 성공 (시도 {attempt}회, score={result['score']})")
            return result
        except Exception as e:
            print(f"Fear & Greed 시도 {attempt}/{max_retries} 실패: {e}")
            if attempt < max_retries:
                time.sleep(2)

    # 모든 시도 실패 → 캐시 사용
    try:
        with open(CACHE_FILE, 'r') as f:
            cached = json.load(f)
            cached['cached'] = True
            print(f"Fear & Greed 캐시 사용 (score={cached['score']})")
            return cached
    except Exception:
        print("Fear & Greed 캐시도 없음")
        return None


def fetch_vix():
    try:
        h = yf.Ticker("^VIX").history(period="5d")
        if h.empty: return None
        cur  = h['Close'].iloc[-1]
        prev = h['Close'].iloc[-2] if len(h)>=2 else cur
        chg  = cur - prev
        return {'current':round(cur,2),'change':round(chg,2),
                'pct':round(chg/prev*100 if prev else 0,2)}
    except Exception as e:
        print(f"VIX 오류: {e}")
        return None

# ── 게이지 ─────────────────────────────────────────────────
def draw_gauge(ax, cx, cy, score, prev_score, rating, prev_rating):
    outer_r, inner_r = 34, 21

    # 트랙 배경 (연한 회색)
    ax.add_patch(Wedge((cx,cy), outer_r+0.5, 0, 180,
                       width=inner_r+1.5,
                       facecolor='#EEEEEE', edgecolor='none', zorder=2))

    # 5구간 세그먼트
    for (lo,hi), color, lbl in zip(FG_RNG, FG_SEG, FG_LBL):
        sd = 180-(hi/100)*180
        ed = 180-(lo/100)*180
        ax.add_patch(Wedge((cx,cy), outer_r, sd+1.2, ed-1.2,
                           width=outer_r-inner_r,
                           facecolor=color, edgecolor='white',
                           linewidth=2.5, alpha=1.0, zorder=3))
        mid_rad = np.radians((sd+ed)/2)
        # 글자를 표(웨지) 안으로 이동: (outer_r + inner_r) / 2
        mid_r = (outer_r + inner_r) / 2
        lx = cx + mid_r * np.cos(mid_rad)
        ly = cy + mid_r * np.sin(mid_rad)
        ax.text(lx, ly, lbl, ha='center', va='center',
                fontsize=10.5, color='#000000', fontweight='black', zorder=5)

    # 바늘
    angle_rad = np.radians(180-(score/100)*180)
    nx = cx+28*np.cos(angle_rad)
    ny = cy+28*np.sin(angle_rad)
    ax.annotate('', xy=(nx,ny), xytext=(cx,cy),
                arrowprops=dict(arrowstyle='->', color='#222222',
                                lw=5.0, mutation_scale=22), zorder=7)
    ax.add_patch(Circle((cx,cy), 3.2, facecolor='#222222', zorder=8))
    ax.add_patch(Circle((cx,cy), 1.6, facecolor='white', zorder=9))

    # 점수
    sc = score_text_color(score)
    ax.text(cx, cy-3.5, f'{score:.0f}',
            ha='center', va='top', fontsize=50,
            fontweight='black', color=sc, zorder=10)

    # 등급
    ax.text(cx, cy-13.0, to_kr(rating),
            ha='center', va='center', fontsize=20,
            fontweight='bold', color=sc, zorder=10)

    # 전일 비교
    ax.text(cx, cy-16.5,
            f'전일  {prev_score:.0f}  ({to_kr(prev_rating)})',
            ha='center', va='center', fontsize=11,
            fontweight='bold', color=SUBTEXT, zorder=10)

# ── VIX 섹션 ──────────────────────────────────────────────
def draw_vix_content(ax, cx, cy, vix):
    cur = vix['current']
    chg = vix['change']
    pct = vix['pct']
    vc  = score_text_color(100 - min(cur/80*100, 100))  # VIX는 높을수록 위험
    vc  = vix_color(cur)
    # VIX 텍스트 색은 진하게
    vc_text = '#CC2222' if cur>35 else ('#CC7700' if cur>25 else ('#AA8800' if cur>15 else '#226622'))

    arrow = '▲' if chg >= 0 else '▼'
    cc    = '#CC4444' if chg >= 0 else '#3377CC'

    # 수치
    ax.text(cx, cy+11, f'{cur:.2f}',
            ha='center', va='center', fontsize=55,
            fontweight='black', color=vc_text, zorder=5)
    ax.text(cx, cy+2.0, f'{arrow}  {abs(chg):.2f}  ({abs(pct):.2f}%)',
            ha='center', va='center', fontsize=20,
            fontweight='bold', color=cc, zorder=5)

    # 단계 바
    segs = [(0,15,VIX_SEG[0],'안정\n(~15)'),
            (15,25,VIX_SEG[1],'보통\n(~25)'),
            (25,35,VIX_SEG[2],'주의\n(~35)'),
            (35,80,VIX_SEG[3],'공포\n(35+)')]
    total = 80
    bx, bw, by, bh = cx-44, 88, cy-8, 7

    for lo, hi, color, label in segs:
        sw = (hi-lo)/total*bw
        sx = bx+(lo/total)*bw
        rect = FancyBboxPatch((sx+0.15, by), sw-0.3, bh,
                              boxstyle='round,pad=0.3',
                              facecolor=color, edgecolor='white',
                              linewidth=2.5, zorder=3)
        ax.add_patch(rect)
        ax.text(sx+sw/2, by+bh/2, label,
                ha='center', va='center', fontsize=12.5,
                color='#000000', fontweight='black', zorder=4)

    # 현재 마커
    clamped = min(cur, 80)
    mx = bx+(clamped/total)*bw
    ax.annotate('', xy=(mx, by+bh+0.4), xytext=(mx, by+bh+4.5),
                arrowprops=dict(arrowstyle='->', color='#333333',
                                lw=2.2, mutation_scale=12), zorder=6)
    ax.text(mx, by+bh+5, f'{cur:.1f}',
            ha='center', va='bottom', fontsize=14,
            fontweight='black', color='#000000', zorder=6)

# ── 메인 ──────────────────────────────────────────────────
def create_sentiment_image(output_path='sentiment_monitoring.png'):
    fg  = fetch_fear_and_greed()
    vix = fetch_vix()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    # 정사각 figure → equal aspect → 100x100 완벽 매핑
    fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect('equal')
    ax.axis('off')

    # ── 제목 (Fear & Greed Index) ──────────────────────────
    ax.text(50, 97.0, 'Fear & Greed Index',
            ha='center', va='center', fontsize=20,
            fontweight='black', color=TITLE, zorder=5)
    ax.text(96, 97.0, f'조회 기준: {now_str}',
            ha='right', va='center', fontsize=10,
            fontweight='bold', color=SUBTEXT, zorder=5)

    # ── Fear & Greed 섹션 ──────────────────────────────────
    if fg:
        draw_gauge(ax, 50, 57, fg['score'], fg['prev_score'],
                   fg['rating'], fg['prev_rating'])
        if fg.get('cached'):
            ax.text(50, 40, '* 이전 저장 데이터 사용 중',
                    ha='center', va='center', fontsize=8.5,
                    color='#AAAAAA', style='italic', zorder=10)
    else:
        ax.text(50, 56, 'Fear & Greed 데이터 조회 실패',
                ha='center', va='center', fontsize=12,
                color=SUBTEXT, zorder=5)

    # ── 구분선 ────────────────────────────────────────────
    ax.plot([4, 96], [38.0, 38.0], color=DIVIDER, linewidth=1.5, zorder=4)

    # ── VIX 섹션 ──────────────────────────────────────────
    ax.text(50, 34.0, 'VIX  변동성 지수',
            ha='center', va='center', fontsize=20,
            fontweight='black', color=TEXT, zorder=5)

    if vix:
        draw_vix_content(ax, 50, 14, vix)
    else:
        ax.text(50, 14, 'VIX 데이터 조회 실패',
                ha='center', va='center', fontsize=12,
                color=SUBTEXT, zorder=5)

    plt.savefig(output_path, dpi=100,
                bbox_inches='tight', pad_inches=0.05)
    plt.close()
    print(f"이미지 저장 완료: {output_path}")
    return output_path

if __name__ == '__main__':
    output = create_sentiment_image('sentiment_monitoring.png')
    notify(
        image_paths=[output],
        subject='[시장심리] Fear & Greed / VIX 지수',
        body='시장 심리 지표 이미지를 확인하세요.'
    )
