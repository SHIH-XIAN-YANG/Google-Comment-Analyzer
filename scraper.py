import time
import requests
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def expand_url(short_url):
    """還原短網址"""
    try:
        # 偽裝成瀏覽器，避免 Google 直接拒絕連線
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        }
        response = requests.get(short_url, headers=headers, allow_redirects=True)
        return response.url
    except Exception as e:
        print(f"URL 解析錯誤: {e}")
        return short_url

def scrape_google_reviews(url, max_reviews=10):
    print(f"正在處理連結: {url}")
    
    chrome_options = Options()
    # chrome_options.add_argument("--headless") # 測試時建議先不開 headless
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--lang=zh-TW") # 強制中文介面
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(url)
        time.sleep(3) # 等待初次載入

        # --- 關鍵修正：檢測是否誤入 Google Search 頁面 ---
        current_url = driver.current_url
        if "/search?" in current_url:
            print("偵測到這是 Google 搜尋頁面，正在嘗試切換至 Google 地圖模式...")
            
            # 方法 1: 從網址中提取搜尋關鍵字，重新組合成 Maps 連結
            # 搜尋網址通常長這樣: ...google.com/search?q=Seed+Bakery...
            parsed_url = urllib.parse.urlparse(current_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            if 'q' in query_params:
                search_query = query_params['q'][0]
                # 重新導向到 Google Maps 搜尋介面
                new_map_url = f"https://www.google.com/maps/search/{search_query}"
                print(f"重新導向至: {new_map_url}")
                driver.get(new_map_url)
                time.sleep(5) # 等待地圖載入
            else:
                print("無法提取關鍵字，嘗試直接尋找地圖按鈕...")
        # -----------------------------------------------

        # 嘗試尋找滾動容器
        # 策略更新：嘗試多種常見的 Selector
        scrollable_div = None
        selectors = [
            'div[role="feed"]',  # 最常見的
            'div.m6QErb.DxyBCb.kA9KIf.dS8AEf', # 另一種常見結構
            'div.e07Vkf.kA9KIf'
        ]
        
        for selector in selectors:
            try:
                scrollable_div = driver.find_element(By.CSS_SELECTOR, selector)
                if scrollable_div:
                    print(f"成功定位滾動區塊: {selector}")
                    break
            except:
                continue

        if scrollable_div:
            print("開始滾動載入評論...")
            for _ in range(0, max_reviews, 5): 
                driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                time.sleep(2) 
        else:
            print("⚠️ 警告：找不到滾動區塊，將只抓取目前畫面可見的評論。")

        # 解析 HTML
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 抓取評論卡片 (這裡也要多種策略，因為 Google Class 常變)
        review_blocks = soup.find_all("div", class_="jftiEf")
        if not review_blocks:
             # 如果 jftiEf 找不到，嘗試找比較通用的結構
             review_blocks = soup.select('div[data-review-id]')

        print(f"找到 {len(review_blocks)} 個評論區塊")

        cleaned_data = []
        for block in review_blocks:
            try:
                # 嘗試抓取作者
                author = block.find("div", class_="d4r55")
                if not author: author = block.get("aria-label") # 有時候作者名在屬性裡
                author_text = author.text.strip() if author else "未知用戶"
                
                # 嘗試抓取內容
                content_elem = block.find("span", class_="wiI7pd")
                content = content_elem.text.strip() if content_elem else "(無文字評論)"
                
                # 嘗試抓取星等
                stars_elem = block.find("span", class_="kvMYJc")
                rating = "0"
                if stars_elem:
                    aria = stars_elem.get("aria-label") # 例如 "5 顆星"
                    if aria:
                        import re
                        match = re.search(r'\d+', aria)
                        if match: rating = match.group()

                cleaned_data.append({
                    "author": author_text,
                    "rating": rating,
                    "content": content
                })
            except Exception as loop_e:
                print(f"解析單一評論失敗: {loop_e}")
                continue
                
        return cleaned_data

    except Exception as e:
        print(f"爬蟲發生錯誤: {e}")
        return []
    finally:
        driver.quit()