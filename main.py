import requests
from bs4 import BeautifulSoup
import json
import os
import time
import sys

# ====== 設定 ======
# テスト時は True、本番稼働時は False に変更してください
TEST_MODE = True  

TARGET_URL = "https://maniacs1091.jp/blog/category/%e5%85%a5%e8%8d%b7%e6%83%85%e5%a0%b1/%e3%83%88%e3%83%a9%e3%82%a6%e3%83%88/"
DB_FILE = "notified_urls.json"
MAX_LIMIT = 5  # 安全装置：この件数以上ならLINE通知を遮断しDBのみ更新
LINE_TOKEN = os.environ.get("LINE_TOKEN", "") 

# デザイン設定
THEME_COLOR = "#555555" # シックなダークグレー
# GitHubにアップロードされた小文字の「logo.png」のURLを指定
LOGO_URL = "https://raw.githubusercontent.com/harackgm/maniacs-blog-bot/main/logo.png"
# ==================

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data[-100:], f, ensure_ascii=False, indent=2)

def send_line_carousel(posts):
    """LINE Flex Message (Carousel) を作成し送信する"""
    if not LINE_TOKEN:
        print("[スキップ] LINE_TOKEN未設定のため擬似通知（カルーセル）")
        return

    bubbles = []
    for post in posts:
        bubble = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "image",
                        "url": LOGO_URL,
                        "size": "sm",
                        "aspectMode": "fit",
                        "align": "start"
                    }
                ],
                "paddingAll": "10px",
                "backgroundColor": "#ffffff"
            },
            "hero": {
                "type": "image",
                "url": post['image_url'],
                "size": "full",
                "aspectRatio": "20:13",
                "aspectMode": "cover"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "新着入荷: トラウト",
                        "weight": "bold",
                        "color": THEME_COLOR,
                        "size": "sm"
                    },
                    {
                        "type": "text",
                        "text": post['title'],
                        "weight": "bold",
                        "size": "md",
                        "wrap": True,
                        "margin": "md"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": THEME_COLOR,
                        "action": {
                            "type": "uri",
                            "label": "記事を読む",
                            "uri": post['url']
                        }
                    }
                ]
            }
        }
        bubbles.append(bubble)

    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messages": [
            {
                "type": "flex",
                "altText": "トラウト入荷の最新記事があります", 
                "contents": {
                    "type": "carousel",
                    "contents": bubbles
                }
            }
        ]
    }
    
    try:
        res = requests.post(url, headers=headers, json=data, timeout=10)
        res.raise_for_status()
        time.sleep(1)
    except Exception as e:
        print(f"LINE通知エラー: {e}")

def get_latest_posts():
    """HTMLページから最新記事とサムネイル画像を取得する"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(TARGET_URL, headers=headers, timeout=10)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.content, "html.parser")
        articles = soup.find_all("article")
        
        posts = []
        for article in articles:
            title_tag = article.find("h2", class_="entry-title")
            if not title_tag or not title_tag.find("a"):
                continue
            
            title = title_tag.text.strip()
            link = title_tag.find("a").get("href")
            
            image_url = ""
            img_tag = article.find("img", class_="wp-post-image")
            if img_tag and img_tag.get("src"):
                image_url = img_tag.get("src").replace("http://", "https://")
            
            if not image_url:
                image_url = "https://placehold.jp/20/cccccc/ffffff/400x260.png?text=No%20Image"

            if link:
                posts.append({"title": title, "url": link, "image_url": image_url})
                
        return posts
    except Exception as e:
        print(f"取得エラー: {e}")
        return []

def main():
    print("--- 巡回開始 ---")
    
    if TEST_MODE:
        print("※ テストモードで実行中（最新1件のみ通知・DB更新なし）")
        
    db_urls = load_db()
    posts = get_latest_posts()
    
    if not posts:
        print("記事が見つかりませんでした。終了します。")
        sys.exit(1)
        
    if TEST_MODE:
        test_post = posts[0] 
        send_line_carousel([test_post])
        print("テスト通知を送信しました。LINEを確認してください。")
        print("--- 巡回完了 ---")
        return
        
    new_posts = [p for p in posts if p["url"] not in db_urls]
    
    if not new_posts:
        print("新着記事はありませんでした。")
        print("--- 巡回完了 ---")
        return

    print(f"新着記事を {len(new_posts)} 件検知しました。")
    
    if len(new_posts) > MAX_LIMIT:
        print(f"【警告】新着件数が上限({MAX_LIMIT}件)を超過しています。")
        print("無料枠の枯渇を防ぐため、LINE通知をスキップしてDBの既読化のみ行います。")
    else:
        send_line_carousel(list(reversed(new_posts)))
    
    for post in new_posts:
        db_urls.append(post["url"])
    
    save_db(db_urls)
    print("--- 巡回完了 ---")

if __name__ == "__main__":
    main()
