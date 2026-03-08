import os
import requests
import urllib.parse
from dotenv import load_dotenv

# 載入 .env 裡的金鑰
load_dotenv()
OUTSCRAPER_API_KEY = os.getenv('OUTSCRAPER_API_KEY')

def expand_url(short_url):
    """
    將短網址還原，如果是 Google 搜尋連結，則提取出精準的店名關鍵字
    """
    print(f"🔄 正在解析網址: {short_url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        # 取得跳轉後的真實網址
        response = requests.get(short_url, headers=headers, allow_redirects=True)
        real_url = response.url
        print(f"🔗 真實網址為: {real_url}")
        
        # 如果是 Google 搜尋結果，把搜尋關鍵字 (q=...) 抽出來當作 Query
        if "/search?" in real_url:
            parsed_url = urllib.parse.urlparse(real_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            if 'q' in query_params:
                # 提取關鍵字並加上 "台灣" 增加準確度
                search_term = query_params['q'][0] + " 台灣"
                print(f"🎯 轉換為精準搜尋關鍵字: {search_term}")
                return search_term
                
        return real_url
    except Exception as e:
        print(f"⚠️ 網址解析錯誤: {e}")
        return short_url

def scrape_google_reviews(query, max_reviews=50):
    print(f"🚀 正在發送請求至 Outscraper API: {query}")
    
    if not OUTSCRAPER_API_KEY:
        print("❌ 找不到 OUTSCRAPER_API_KEY")
        return []

    api_url = "https://api.app.outscraper.com/maps/reviews-v3"
    
    params = {
        "query": query,  
        "reviewsLimit": max_reviews, 
        "language": "zh-TW",      
        "sort": "newest",         
        "ignoreEmpty": "false",
        "async": "false" # 強制同步回傳
    }
    
    headers = {
        "X-API-KEY": OUTSCRAPER_API_KEY
    }
    
    try:
        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status() 
        data = response.json()
        
        if "data" in data and len(data["data"]) > 0:
            shop_data = data["data"][0] 
            
            # 檢查是否真的有找到地點
            if shop_data.get("place_id") == "__NO_PLACE_FOUND__":
                print("❌ Outscraper 找不到該地點，請確認網址或店名是否正確。")
                return []
                
            raw_reviews = shop_data.get("reviews_data", [])
            print(f"✅ 成功抓取到 {len(raw_reviews)} 則評論！")
            
            cleaned_data = []
            for rev in raw_reviews:
                cleaned_data.append({
                    "author": rev.get("author_title", "未知用戶"),
                    "rating": rev.get("review_rating", 0),
                    "date": rev.get("review_datetime_utc", ""), 
                    "content": rev.get("review_text", "(無文字)"),
                })
            return cleaned_data
        else:
            return []

    except Exception as e:
        print(f"❌ API 請求失敗: {e}")
        return []

# --- 單獨測試區塊 ---
if __name__ == "__main__":
    # 測試 1: 給它一個絕對不會錯的 Google Maps 完整長網址 (台北101)
    test_query = "https://www.google.com/maps/place/%E5%8F%B0%E5%8C%97101%E8%A7%80%E6%99%AF%E5%8F%B0/@25.0336793,121.5621494,17z/data=!3m1!4b1!4m6!3m5!1s0x3442abb6da80a7ad:0xacc4d11dc963103c!8m2!3d25.0336745!4d121.5647243!16s%2Fg%2F11b6_c2v6_?entry=ttu"
    
    # 我們先過水一下 expand_url 函數
    final_query = expand_url(test_query)
    
    reviews = scrape_google_reviews(final_query, max_reviews=5)
    import json
    print(json.dumps(reviews, ensure_ascii=False, indent=2))