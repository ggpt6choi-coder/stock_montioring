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
        # 맵이 충분히 보이도록 뷰포트 설정
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        try:
            page.goto("https://finviz.com/map.ashx?t=sec", wait_until="networkidle", timeout=60000)
            
            # 팝업 닫기 시도
            try:
                if page.locator("button:has-text('Accept')").is_visible():
                    page.click("button:has-text('Accept')", timeout=5000)
            except: pass
            
            page.wait_for_selector("#map-canvas-container", timeout=20000)
            time.sleep(3) 
            
            # 맵 영역만 스크린샷 (임시 저장)
            map_container = page.locator("#map-canvas-container")
            map_container.screenshot(path=temp_path)
            
            # ── 인스타그램 규격(1080x1080)으로 재가공 ────────────────
            fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
            fig.patch.set_facecolor('#F8F9FA')
            ax.set_facecolor('#F8F9FA')
            ax.set_xlim(0, 100)
            ax.set_ylim(0, 100)
            ax.axis('off')
            
            # 제목 및 날짜
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            ax.text(50, 96, 'S&P 500 Market Heatmap', ha='center', va='center', 
                    fontsize=24, fontweight='black', color='#000000')
            ax.text(96, 96, f'조회 기준: {now_str}', ha='right', va='center', 
                    fontsize=10, fontweight='bold', color='#666666')
            
            # 맵 이미지 불러오기 및 중앙 배치
            img = mpimg.imread(temp_path)
            img_h, img_w, _ = img.shape
            aspect = img_h / img_w
            
            # 가로 92% 폭을 사용하고 세로는 비율에 맞춰 계산
            target_w = 92
            target_h = target_w * aspect
            
            # Y축 중앙 부근에 배치 (상단 제목 공간 제외)
            y_start = (90 - target_h) / 2 + 5 
            
            ax.imshow(img, extent=[4, 96, y_start, y_start + target_h], aspect='auto', zorder=2)
            
            # 테두리 장식 (선택 사항)
            rect = plt.Rectangle((4, y_start), 92, target_h, linewidth=2, edgecolor='#E0E0E0', facecolor='none', zorder=3)
            ax.add_patch(rect)
            
            plt.savefig(output_path, bbox_inches='tight', pad_inches=0.05, facecolor=fig.get_facecolor())
            plt.close()
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            print(f"인스타그램 규격 시장 맵 저장 완료: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"시장 맵 캡처 중 오류 발생: {e}")
            return None
        finally:
            browser.close()

if __name__ == "__main__":
    capture_market_map()
