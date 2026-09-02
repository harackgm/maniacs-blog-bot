import requests
from bs4 import BeautifulSoup
import json
import os
import time
import sys

# ====== 設定 ======
# テスト時は True、本番稼働時は False に変更してください
TEST_MODE = True  

TARGET_URL = "https://maniacs1091.jp/blog/category/%e5%85%a5%e8%8d%b7%e6%83%85%e5%a0%b1/%e3%83%88%e3%83%a9%e3%82%a6%e3%83%88/feed/"
DB_FILE = "notified_urls.json"
MAX_LIMIT = 5  # 安全装置：この件数以上ならLINE通知を遮断しDBのみ更新
LINE_TOKEN = os.environ.get("LINE_TOKEN", "") 
# ==================

def format_message(post):
    """
    【デザイン変更用ブロック】
    LINEに通知するメッセージの見た目をここで自由に変更できます。
    post['title'] には記事のタイトル、post['url'] にはURLが入ります。
    \n は改行を意味します。
    """
    msg = f"🐟【新着入荷:トラウト】🐟\n\n📝 {post['title']}\n\n🔗 リンクはこちら:\n{post['url']}"
    return msg

def load_db():
    """過去の通知済みURLリストを読み込む"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_db(data):
    """通知済みURLリストを保存する（最大100件）"""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data[-100:], f, ensure_ascii=False, indent=2)

def send_line_message(message):
    """LINE Messaging API (Broadcast) へメッセージを送信する"""
    if not LINE_TOKEN:
        print(f"[スキップ] LINE_TOKEN未設定のため擬似通知:\n{message}")
        return
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messages": [
            {
                "type": "text",
                "text": message
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
    """RSSフィードから最新記事を取得する"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(TARGET_URL, headers=headers, timeout=10)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")
        
        posts = []
        for item in items:
            title = item.title.text.strip() if item.title else "No Title"
            link = item.link.text.strip() if item.link else ""
            if link:
                posts.append({"title": title, "url": link})
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
        
    # --- テストモードの処理 ---
    if TEST_MODE:
        test_post = posts[0] # 一番最新の記事を1つだけ取り出す
        msg = format_message(test_post)
        send_line_message(msg)
        print("テスト通知を送信しました。LINEを確認してください。")
        print("--- 巡回完了 ---")
        return
        
    # --- 本番モードの処理 ---
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
        for post in reversed(new_posts): 
            msg = format_message(post)
            send_line_message(msg)
    
    for post in new_posts:
        db_urls.append(post["url"])
    
    save_db(db_urls)
    print("--- 巡回完了 ---")

if __name__ == "__main__":
    main()
