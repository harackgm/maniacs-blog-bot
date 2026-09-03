import requests
from bs4 import BeautifulSoup
import json
import os
import time
import sys

# ====== 設定 ======
# 本番稼働モード（差分検知による新着通知のみ実行）
TEST_MODE = False  

TARGET_URL = "https://maniacs1091.jp/blog/category/%e5%85%a5%e8%8d%b7%e6%83%85%e5%a0%b1/%e3%83%88%e3%83%a9%e3%82%a6%e3%83%88/"
DB_FILE = "notified_urls.json"
MAX_LIMIT = 5  # 大量通知ストッパー（安全装置）
LINE_TOKEN = os.environ.get("LINE_TOKEN", "") 

# デザイン設定（指定通り変更なし）
THEME_COLOR = "#555555" 
LOGO_URL = "https://github.com/user-attachments/assets/ff604851-38f5-4ced-94aa-93a07340c96c"
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
                        "size": "full",
                        "aspectRatio": "4:1", 
                        "aspectMode": "fit",
                        "align": "center"
                    }
                ],
                "paddingAll": "0px", 
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
        res = requests.post(url, headers=headers, json=data, timeout=15)
        res.raise_for_status()
        time.sleep(1)
    except Exception as e:
        print(f"LINE通知エラー: {e}")

def get_latest_posts():
    """HTMLページから最新記事とサムネイル画像を取得する（ゆらぎ・崩れ防止強化）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # ネットワークゆらぎ対策（リトライ処理）
    res = None
    for attempt in range(3):
        try:
            res = requests.get(TARGET_URL, headers=headers, timeout=15)
            res.raise_for_status()
            break
        except Exception as e:
            print(f"接続試行 {attempt + 1} 回目失敗: {e}")
            time.sleep(2)
            
    if not res:
        print("サイトへの接続に失敗しました。")
        return []

    try:
        soup = BeautifulSoup(res.content, "html.parser")
        articles = soup.find_all("article")
        
        posts = []
        for article in articles:
            # タイトルとリンクの取得
            title_tag = article.find("h2", class_="entry-title")
            if not title_tag or not title_tag.find("a"):
                continue
            
            title = title_tag.text.strip().replace("\n", "").replace("\r", "")
            link = title_tag.find("a").get("href", "").strip()
            
            # サムネイル画像の強固な抽出（src, data-src, srcsetに対応）
            image_url = ""
            img_tag = article.find("img", class_="wp-post-image")
            
            if img_tag:
                # 優先順位: data-src > src > srcsetの先頭URL
                image_url = img_tag.get("data-src") or img_tag.get("src") or ""
                if not image_url and img_tag.get("srcset"):
                    image_url = img_tag.get("srcset").split(",")[0].split(" ")[0]
            
            # HTTP -> HTTPS 補正
            if image_url:
                image_url = image_url.replace("http://", "https://")
            else:
                image_url = "https://placehold.jp/20/cccccc/ffffff/400x260.png?text=No%20Image"

            if link:
                posts.append({"title": title, "url": link, "image_url": image_url})
                
        return posts
    except Exception as e:
        print(f"解析エラー: {e}")
        return []

def main():
    print("--- 巡回開始 ---")
    
    if TEST_MODE:
        print("※ テストモードで実行中（最新1件のみ通知・DB更新なし）")
        
    db_urls = load_db()
    posts = get_latest_posts()
    
    if not posts:
        print("記事が見つかりませんでした。終了します。")
        sys.exit(0) # 異常終了にせず正常終了
        
    if TEST_MODE:
        test_post = posts[0] 
        send_line_carousel([test_post])
        print("テスト通知を送信しました。LINEを確認してください。")
        print("--- 巡回完了 ---")
        return
        
    # 未既読チェック
    new_posts = [p for p in posts if p["url"] not in db_urls]
    
    if not new_posts:
        print("新着記事はありませんでした。")
        print("--- 巡回完了 ---")
        return

    print(f"新着記事を {len(new_posts)} 件検知しました。")
    
    # 大量通知ストッパー（MAX_LIMIT制御）
    if len(new_posts) > MAX_LIMIT:
        print(f"【警告】新着件数が上限({MAX_LIMIT}件)を超過しています。")
        print("無料枠の枯渇を防ぐため、LINE通知をスキップしてDBの既読化のみ行います。")
    else:
        # 古い順に並び替えて送信
        send_line_carousel(list(reversed(new_posts)))
    
    # DB更新
    for post in new_posts:
        if post["url"] not in db_urls:
            db_urls.append(post["url"])
    
    save_db(db_urls)
    print("--- 巡回完了 ---")

if __name__ == "__main__":
    main()
