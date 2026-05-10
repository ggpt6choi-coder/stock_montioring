import os
import time
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from datetime import datetime
import matplotlib

# 한글 폰트 설정 (OS별 처리)
import platform
system_name = platform.system()
if system_name == 'Darwin':
    matplotlib.rc('font', family='AppleGothic')
elif system_name == 'Linux':
    matplotlib.rc('font', family='NanumGothic')

def capture_market_map(output_path='market_map.png'):
    print("시장 맵(Finviz) 캡처 및 인스타그램 규격 변환을 시작합니다...")
    temp_path = 'temp_map.png'
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 현실적인 User-Agent와 설정 적용
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        try:
            # 타임아웃을 넉넉히 주고 로드 시점 조절
            page.goto("https://finviz.com/map.ashx?t=sec", wait_until="domcontentloaded", timeout=60000)
            
            # 페이지 로드 후 맵과 모달이 나타날 때까지 충분히 대기
            time.sleep(15) 
            
            # JavaScript로 모든 모달, 오버레이 및 높은 z-index 요소 강제 제거
            page.evaluate("""() => {
                // 1. 일반적인 모달/오버레이 클래스 패턴 제거
                const selectors = [
                    '[class*="modal"]', '[id*="modal"]', 
                    '[class*="overlay"]', '[id*="overlay"]',
                    '.absolute.top-0.left-0.w-full.h-full',
                    'button.absolute.right-4'
                ];
                selectors.forEach(s => {
                    document.querySelectorAll(s).forEach(el => el.remove());
                });
                
                // 2. 높은 z-index를 가진 모든 요소 제거 (모달 대응, 맵 본체는 제외)
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    const z = parseInt(window.getComputedStyle(el).zIndex);
                    if (z > 100 && el.id !== 'map-canvas' && !el.closest('#map-canvas-container')) {
                        el.remove();
                    }
                }
                
                // 3. 스크롤 막힘 해제 및 배경 흐림 제거
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            }""")
            print("모달 제거 스크립트 실행 완료")
            time.sleep(3)
            
            # 맵 영역 확인 및 캡처 (여러 셀렉터 시도)
            # 1. 명시적인 ID로 시도
            map_element = page.locator("canvas#map-canvas")
            
            # 2. 만약 못 찾으면 페이지 내에서 가장 큰 캔버스 요소를 찾음 (히트맵 특성상 가장 큼)
            if map_element.count() == 0 or not map_element.first.is_visible():
                print("명시적 ID로 맵을 찾지 못했습니다. 대체 검색을 시작합니다...")
                canvases = page.query_selector_all("canvas")
                max_area = 0
                best_canvas = None
                for c in canvases:
                    box = c.bounding_box()
                    if box:
                        area = box['width'] * box['height']
                        if area > max_area:
                            max_area = area
                            best_canvas = c
                
                if best_canvas and max_area > 100000: # 최소 10만 픽셀 이상 (예: 500x200)
                    map_element = best_canvas
                    print(f"가장 큰 캔버스 발견: {max_area}px 영역")
                else:
                    # 마지막 수단: 컨테이너 시도
                    map_element = page.locator("#map-canvas-container").first
            else:
                map_element = map_element.first
            
            if not map_element:
                 raise Exception("맵 요소를 도저히 찾을 수 없습니다.")
            
            # 요소가 화면에 보이도록 대기
            map_element.screenshot(path=temp_path)
            
            # ── 인스타그램 규격(1080x1080)으로 재가공 ────────────────
            fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
            # 맵 배경색과 유사한 어두운 색상 적용 (더 꽉 찬 느낌을 줌)
            BG_DARK = '#161C22' 
            fig.patch.set_facecolor(BG_DARK)
            ax.set_facecolor(BG_DARK)
            ax.set_xlim(0, 100)
            ax.set_ylim(0, 100)
            ax.axis('off')
            
            # 제목 및 날짜 (어두운 배경에 맞춰 흰색 계열로)
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            ax.text(50, 96, 'S&P 500 Market Heatmap', ha='center', va='center', 
                    fontsize=26, fontweight='black', color='#FFFFFF')
            ax.text(96, 96, f'조회 기준: {now_str}', ha='right', va='center', 
                    fontsize=10, fontweight='bold', color='#AAAAAA')
            
            # 맵 이미지 불러오기 및 중앙 배치
            img = mpimg.imread(temp_path)
            img_h, img_w, _ = img.shape
            aspect = img_h / img_w
            
            # 가로를 거의 100% 가깝게 채움 (여백 최소화)
            target_w = 98
            target_h = target_w * aspect
            
            # 중앙 배치 (Y축 여백 최소화)
            y_start = (92 - target_h) / 2 + 2
            
            ax.imshow(img, extent=[1, 99, y_start, y_start + target_h], aspect='auto', zorder=2)
            
            # 테두리 제거 또는 아주 얇게
            plt.savefig(output_path, bbox_inches='tight', pad_inches=0, facecolor=fig.get_facecolor())
            plt.close()
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            print(f"인스타그램 규격 시장 맵 저장 완료: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"시장 맵 캡처 중 오류 발생: {e}")
            try:
                page.screenshot(path='debug_error.png')
                print("디버깅용 전체 화면 스크린샷 저장 완료: debug_error.png")
            except: pass
            return None
        finally:
            browser.close()

if __name__ == "__main__":
    capture_market_map()
