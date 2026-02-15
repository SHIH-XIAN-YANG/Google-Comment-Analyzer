# app.py
import os
import threading
import json

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 引入 dotenv
from dotenv import load_dotenv

# 載入我們寫的爬蟲
from scraper import expand_url, scrape_google_reviews

# 1. 載入 .env 檔案
load_dotenv()
app = Flask(__name__)


# 2. 從環境變數中讀取設定
# os.getenv('變數名稱') 會回傳該變數的值，如果沒找到會回傳 None
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')

# 3. 安全檢查：確保有讀到變數，否則程式直接報錯停止 (避免後續運作錯誤)
if channel_access_token is None:
    print("錯誤：找不到 LINE_CHANNEL_ACCESS_TOKEN，請檢查 .env 檔案！")
    sys.exit(1)
if channel_secret is None:
    print("錯誤：找不到 LINE_CHANNEL_SECRET，請檢查 .env 檔案！")
    sys.exit(1)

# 初始化 LINE Bot API
line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# --- 背景任務函數 ---
def heavy_task(user_id, raw_url):
    """這是在背景執行的爬蟲任務"""
    try:
        # 1. 還原網址
        real_url = expand_url(raw_url)
        
        # 2. 執行爬蟲
        reviews = scrape_google_reviews(real_url, max_reviews=10)
        
        if not reviews:
            line_bot_api.push_message(user_id, TextSendMessage(text="❌ 抓取失敗，可能是連結錯誤或 Google 改版了。"))
            return

        # 3. 整理結果 (這裡先用純文字回傳 JSON，之後再接 OpenAI)
        result_text = f"✅ 成功抓取 {len(reviews)} 則評論！\n\n(顯示前 3 則):\n"
        json_output = json.dumps(reviews[:3], ensure_ascii=False, indent=2)
        
        final_msg = result_text + json_output
        
        # 4. 主動推播結果給使用者
        line_bot_api.push_message(user_id, TextSendMessage(text=final_msg[:2000]))
        
    except Exception as e:
        print(f"Task Error: {e}")
        line_bot_api.push_message(user_id, TextSendMessage(text=f"❌ 系統錯誤: {e}"))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    user_id = event.source.user_id
    
    # 簡單判斷是否為網址
    if "http" in msg and ("google" in msg or "goo.gl" in msg):
        # 1. 先回覆使用者「處理中」
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔍 收到 Google Maps 連結！\n正在啟動瀏覽器抓取評論，請稍候約 15-30 秒...")
        )
        
        # 2. 開啟新執行緒去跑爬蟲 (才不會卡住)
        task_thread = threading.Thread(target=heavy_task, args=(user_id, msg))
        task_thread.start()
        
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請貼上 Google Maps 的店家分享連結給我喔！")
        )

if __name__ == "__main__":
    app.run(port=5000)