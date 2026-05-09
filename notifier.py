import os
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# [설정] 발송 제어 플래그 (True: 활성화, False: 비활성화)
# ==========================================
ENABLE_EMAIL = False
ENABLE_TELEGRAM = True
# ==========================================

def send_image_via_gmail(image_paths, subject="주식 모니터링 결과", body="첨부된 이미지를 확인하세요."):
    sender_email = os.getenv('SENDER_EMAIL')
    app_password = os.getenv('APP_PASSWORD')
    receiver_email = os.getenv('RECEIVER_EMAIL')

    if not all([sender_email, app_password, receiver_email]):
        print("이메일 설정 정보가 부족합니다. .env 파일을 확인해주세요.")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    for idx, image_path in enumerate(image_paths):
        if not os.path.exists(image_path):
            print(f"파일을 찾을 수 없습니다: {image_path}")
            continue
        with open(image_path, 'rb') as f:
            mime = MIMEBase('image', 'png', filename=os.path.basename(image_path))
            mime.add_header('Content-Disposition', 'attachment', filename=os.path.basename(image_path))
            mime.add_header('X-Attachment-Id', str(idx))
            mime.add_header('Content-ID', f'<{idx}>')
            mime.set_payload(f.read())
            encoders.encode_base64(mime)
            msg.attach(mime)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        print('이메일 전송 완료!')
    except Exception as e:
        print(f"이메일 전송 실패: {e}")

def send_image_via_telegram(image_paths, caption="주식 모니터링 결과입니다."):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not all([token, chat_id]):
        print("텔레그램 설정 정보가 부족합니다. .env 파일을 확인해주세요.")
        return

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    for image_path in image_paths:
        if not os.path.exists(image_path):
            print(f"파일을 찾을 수 없습니다: {image_path}")
            continue
        try:
            with open(image_path, 'rb') as image_file:
                files = {'photo': image_file}
                data = {'chat_id': chat_id, 'caption': caption}
                response = requests.post(url, files=files, data=data)
                if response.status_code == 200:
                    print(f"텔레그램 전송 완료: {os.path.basename(image_path)}")
                else:
                    print(f"텔레그램 전송 실패: {response.text}")
        except Exception as e:
            print(f"텔레그램 전송 중 오류 발생: {e}")

def notify(image_paths, subject="주식 모니터링 결과", body="주식 모니터링 결과입니다."):
    if ENABLE_TELEGRAM:
        send_image_via_telegram(image_paths, caption=subject)
    
    if ENABLE_EMAIL:
        send_image_via_gmail(image_paths, subject=subject, body=body)

    if not ENABLE_EMAIL and not ENABLE_TELEGRAM:
        print("활성화된 알림 채널이 없습니다. (notifier.py 상단의 ENABLE_EMAIL, ENABLE_TELEGRAM 확인)")
