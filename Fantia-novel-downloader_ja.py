import os
import re
import time
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import traceback
import configparser
from typing import List, Dict, Optional

# ==============================================================================
# 設定ファイル管理 (Configuration Management)
# ==============================================================================

def create_default_config(filename: str = "config.ini") -> None:
    """
    デフォルトの設定ファイル(config.ini)を生成する。
    この関数は、設定ファイルが存在しない場合に初回実行時に呼び出される。
    """
    config = configparser.ConfigParser()
    config['Authentication'] = {
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36',
        'cookie': 'ここにブラウザからコピーしたCookie文字列を貼り付けてください',
        'x_csrf_token': 'ここにブラウザからコピーしたX-Csrf-Tokenを貼り付けてください'
    }
    config['Settings'] = {
        'download_scope': 'all',
        'root_output_dir': 'fantia_novels',
        'request_delay': '1.5'
    }
    with open(filename, 'w', encoding='utf-8') as configfile:
        config.write(configfile)
    print(f"INFO: 設定ファイル '{filename}' を生成しました。")
    print("INFO: ファイルを開き、認証情報を入力してからプログラムを再実行してください。")

def load_config(filename: str = "config.ini") -> Optional[configparser.ConfigParser]:
    """
    設定ファイルを読み込む。
    ファイルが存在しない場合は、デフォルトファイルを生成してNoneを返す。

    Args:
        filename (str): 設定ファイル名。

    Returns:
        Optional[configparser.ConfigParser]: 読み込んだ設定オブジェクト。初回生成時はNone。
    """
    if not os.path.exists(filename):
        create_default_config(filename)
        return None
    
    config = configparser.ConfigParser()
    config.read(filename, encoding='utf-8')
    return config

# ==============================================================================
# ユーティリティ関数 (Utility Functions)
# ==============================================================================

def sanitize_filename(filename: str) -> str:
    """
    ファイル名やディレクトリ名として使用できない不正な文字を全角ハイフンに置換する。

    Args:
        filename (str): サニタイズ対象の文字列。

    Returns:
        str: サニタイズ後の文字列。
    """
    invalid_chars = r'[\\/:*?"<>|]'
    return re.sub(invalid_chars, '－', filename)

# ==============================================================================
# コアロジック (Core Logic)
# ==============================================================================

def get_all_post_ids(fanclub_url: str, headers: Dict[str, str], delay: float) -> List[int]:
    """
    指定されたファンクラブの投稿一覧ページを巡回し、全投稿のIDを収集する。
    この関数はHTMLを直接解析(スクレイピング)する。

    Args:
        fanclub_url (str): ファンクラブの投稿一覧ページのURL。
        headers (Dict[str, str]): リクエストに使用するHTTPヘッダー。
        delay (float): 各ページリクエスト間の待機時間（秒）。

    Returns:
        List[int]: 収集した全ての投稿IDのリスト。
    """
    post_ids: List[int] = []
    current_url: Optional[str] = fanclub_url
    page_num = 1
    
    path_segments = urlparse(fanclub_url).path.strip('/').split('/')
    fanclub_id = path_segments[1] if len(path_segments) > 1 else "Unknown"

    print(f"\n--- [Phase 1] ファンクラブID: {fanclub_id} の投稿ID収集を開始 ---")
    
    while current_url:
        print(f"  - ページ {page_num} を走査中...")
        try:
            response = requests.get(current_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ページから取得したJSONデータでログイン状態を確認
            frontend_params_tag = soup.find('script', id='frontend-params')
            if not frontend_params_tag or '"is_logged_in": false' in frontend_params_tag.string:
                 print("\nERROR: ログインに失敗しています。config.iniの'cookie'が無効か期限切れの可能性があります。")
                 return []
            
            links = soup.select('div.module.post a.link-block')
            if not links:
                print("  - このページに投稿リンクが見つかりませんでした。")
                break
                
            for link in links:
                href = link.get('href')
                if href and '/posts/' in href:
                    try:
                        post_id = int(href.split('/')[-1])
                        if post_id not in post_ids:
                            post_ids.append(post_id)
                    except (ValueError, IndexError):
                        continue
            
            next_page_tag = soup.select_one('ul.pagination li.page-item:not(.disabled) a[rel="next"]')
            if next_page_tag and next_page_tag.get('href'):
                current_url = urljoin(fanclub_url, str(next_page_tag['href']))
                page_num += 1
            else:
                current_url = None
                print("  - 最終ページに到達しました。")
            time.sleep(delay)
        except requests.exceptions.RequestException as e:
            print(f"ERROR: ページ '{current_url}' の取得に失敗しました: {e}")
            return []

    print(f"  - ID収集完了。合計 {len(post_ids)} 件の投稿を発見しました。")
    return post_ids

def scrape_and_save_post_api(post_id: int, headers: Dict[str, str], csrf_token: str, root_output_dir: str, scope: str) -> None:
    """
    単一の投稿データをFantia APIから取得し、指定されたスコープに基づいてテキストファイルとして保存する。

    Args:
        post_id (int): 対象の投稿ID。
        headers (Dict[str, str]): リクエストに使用する基本HTTPヘッダー。
        csrf_token (str): APIリクエストに必要なCSRFトークン。
        root_output_dir (str): 保存先ルートディレクトリ。
        scope (str): ダウンロード範囲 ('all', 'paid', 'free')。
    """
    api_url = f"https://fantia.jp/api/v1/posts/{post_id}"
    print(f"  - ID: {post_id} のデータをAPIから取得中...")
    try:
        api_headers = headers.copy()
        api_headers.update({
            'Accept': 'application/json, text/plain, */*',
            'X-Csrf-Token': csrf_token,
            'X-Requested-With': 'XMLHttpRequest',
        })
        
        response = requests.get(api_url, headers=api_headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        post_data = data.get("post")
        if not post_data:
            print(f"  - ERROR: APIレスポンスに投稿データが含まれていません (ID: {post_id})。")
            return

        title = post_data.get("title", f"No Title {post_id}")
        
        # 投稿が有料プラン限定か否かを判定
        is_paid = any(c.get("plan") and c["plan"].get("price", 0) > 0 for c in post_data.get("post_contents", []))

        # 設定されたスコープに基づき、処理をスキップするか判断
        if scope == 'paid' and not is_paid:
            print(f"  - SKIP: 無料投稿はダウンロードスコープ外です ({title})。")
            return
        if scope == 'free' and is_paid:
            print(f"  - SKIP: 有料投稿はダウンロードスコープ外です ({title})。")
            return

        # 有料/無料の異なるJSON構造に対応するため、複数のキーから本文を探索
        full_content = None
        if post_data.get("post_contents"):
            content_parts = [c["comment"] for c in post_data["post_contents"] if c.get("comment")]
            if content_parts:
                full_content = "\n\n".join(content_parts)
        if full_content is None and post_data.get("comment"):
            full_content = post_data["comment"]
        if full_content is None and post_data.get("blog_comment"):
            full_content = post_data["blog_comment"]
        
        if full_content is None:
            print(f"  - WARN: 投稿 {post_id} ({title}) にテキスト本文が見つかりませんでした。")
            return

        # ファンクラブ名のサブディレクトリを作成してファイルを保存
        fanclub_name = post_data.get("fanclub", {}).get("fanclub_name_with_creator_name", f"fanclub_{post_data.get('fanclub', {}).get('id')}")
        sanitized_fanclub_name = sanitize_filename(fanclub_name)
        output_subdir = os.path.join(root_output_dir, sanitized_fanclub_name)
        os.makedirs(output_subdir, exist_ok=True)
        
        filename = sanitize_filename(title) + ".txt"
        filepath = os.path.join(output_subdir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"タイトル: {title}\n")
            f.write(f"URL: https://fantia.jp/posts/{post_id}\n")
            f.write("=" * 40 + "\n\n")
            f.write(full_content)
        print(f"  - OK: 保存完了 -> {filepath}")

    except requests.exceptions.RequestException as e:
        print(f"  - ERROR: APIリクエストに失敗しました (ID: {post_id}): {e}")
    except json.JSONDecodeError:
        print(f"  - ERROR: APIからの応答がJSON形式ではありません (ID: {post_id})。")
    except Exception as e:
        print(f"  - ERROR: 予期せぬエラーが発生しました (ID: {post_id}): {e}")

# ==============================================================================
# メイン実行部 (Main Execution Block)
# ==============================================================================

def main():
    """
    プログラムのメインエントリーポイント。
    設定を読み込み、URLリストに基づいて各ファンクラブの処理を順次実行する。
    """
    print("Fantia-Novel-Downloaderを開始します。")
    try:
        config = load_config()
        if config is None:
            return

        auth_conf = config['Authentication']
        settings_conf = config['Settings']
        
        # 設定値の読み込みと検証
        user_agent = auth_conf.get('user_agent')
        cookie = auth_conf.get('cookie')
        csrf_token = auth_conf.get('x_csrf_token')
        scope = settings_conf.get('download_scope', 'all').lower()
        root_dir = settings_conf.get('root_output_dir', 'fantia_novels')
        delay = settings_conf.getfloat('request_delay', 1.5)

        if "貼り付けてください" in cookie or "貼り付けてください" in csrf_token or not cookie or not csrf_token:
            print("\nERROR: config.ini の 'cookie' または 'x_csrf_token' が設定されていません。")
            return
        if scope not in ['all', 'paid', 'free']:
            print(f"\nERROR: config.ini の 'download_scope' の値が無効です ('{scope}')。'all', 'paid', 'free' のいずれかを指定してください。")
            return

        # DL_links.txt の読み込み
        links_file = "DL_links.txt"
        try:
            with open(links_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and "fantia.jp" in line]
            if not urls:
                print(f"\nERROR: '{links_file}' に有効なURLが記述されていません。")
                return
            print(f"INFO: '{links_file}' から {len(urls)} 件のURLを読み込みました。")
        except FileNotFoundError:
            print(f"\nERROR: '{links_file}' が見つかりません。プログラムと同じ場所に作成し、対象URLを記述してください。")
            return

        base_headers = { 'Cookie': cookie, 'User-Agent': user_agent }
        os.makedirs(root_dir, exist_ok=True)
        print(f"INFO: 保存先ルートディレクトリ: '{os.path.abspath(root_dir)}'")
        print(f"INFO: ダウンロードスコープ: '{scope}'")

        # 各URLを順番に処理
        for url in urls:
            post_ids = get_all_post_ids(url, base_headers, delay)
            if not post_ids:
                print(f"WARN: {url} の処理をスキップします（投稿ID取得失敗）。")
                continue
            
            print(f"\n--- [Phase 2] {len(post_ids)}件の個別投稿ダウンロードを開始 ---")
            for i, post_id in enumerate(post_ids, 1):
                print(f"-> 処理中: {i}/{len(post_ids)}")
                scrape_and_save_post_api(post_id, base_headers, csrf_token, root_dir, scope)
                time.sleep(delay)

        print("\n全ての処理が正常に完了しました。")

    except Exception as e:
        print("\n" + "="*60)
        print("           予期せぬ致命的なエラーが発生しました")
        print("="*60)
        traceback.print_exc()
        print("="*60)
        print(f"ERROR: {e}")
    finally:
        input("\nプログラムを終了するにはEnterキーを押してください...")

if __name__ == '__main__':
    main()