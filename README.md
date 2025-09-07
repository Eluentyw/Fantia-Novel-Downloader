> [!NOTE]
> This is the Japanese version of the README. [Click here for the English version.](./README-en.md)

---

# Fantia-Novel-Downloader_v1.1

## 概要 (Overview)

クリエイター支援プラットフォーム「Fantia」に投稿されたテキストコンテンツを、ローカル環境にテキストファイルとして一括で保存するためのPythonスクリプトです。
ちょうど自分がテキストをアーカイブしたいと思っていて、(自分の調べた限りでは)なぜか誰もやってなかったので作りました。

## 主な機能 (Features)

*   **バッチ処理**: 複数のファンクラブを対象に、一度の実行で全ての小説をダウンロードします。
*   **スコープ指定**: 「すべて」「有料のみ」「無料のみ」から、ダウンロードする投稿の範囲を選択できます。
*   **外部設定ファイル**: 認証情報や動作設定を `config.ini` ファイルで管理します。
*   **体系的なフォルダ生成**: ファンクラブごとにサブフォルダを自動生成し、ダウンロードしたファイルを整理します。

## ⚠︎ 免責事項 (Disclaimer)

*   本ツールは、個人的なバックアップ目的でのみ使用してください。
*   ツールの使用によって生じるいかなる問題（アカウントの制限を含むがこれに限らない）についても、作者は一切の責任を負いません。
*   Fantiaの利用規約を遵守し、サーバーに過度な負荷をかけないよう、自己の責任において本ツールを使用してください。ダウンロードしたコンテンツの再配布や販売は、著作権法に抵触する可能性があります。

---

## 1. システム要件 (Requirements)

*   Python 3.6 以上
*   必要なPythonライブラリ:
    *   `requests`
    *   `beautifulsoup4`

## 2. セットアップ手順 (Setup)

1.  **リポジトリのクローンまたはダウンロード**
    ```bash
    git clone https://github.com/Eluentyw/Fantia-Novel-Downloader.git
    cd Fantia-Novel-Downloader
    ```
    または、ZIPファイルをダウンロードして任意の場所に展開します。

2.  **必要なライブラリのインストール**
    ターミナルまたはコマンドプロンプトで、以下のコマンドを実行します。
    ```bash
    pip install requests beautifulsoup4
    ```

3.  **設定ファイルの準備**
    *   `Fantia-novel-downloader_ja.py` と同じ場所に、`DL-links.txt` というテキストファイルを作成します。
    *   初回実行時に `config.ini` が自動生成されます。

## 3. 設定 (Configuration)

本アプリケーションの動作は、`config.ini` と `DL-links.txt` の2つのファイルによって制御されます。

### 3.1. `config.ini` の設定

このファイルは、初回実行時に自動生成されます。ファイルを開き、必要な情報を追記してください。

```ini
[Authentication]
user_agent = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36
cookie = ここにブラウザからコピーしたCookie文字列を貼り付けてください
x_csrf_token = ここにブラウザからコピーしたX-Csrf-Tokenを貼り付けてください

[Settings]
# ダウンロード範囲: all, paid, free のいずれかを指定
download_scope = all
# ダウンロードしたファイルを保存する一番上のフォルダ名
root_output_dir = fantia_novels
# 各リクエスト間の待機時間（秒）。サーバー負荷軽減のため、1.0以上を推奨
request_delay = 1.5
```

#### **認証情報の取得方法 (`cookie` と `x_csrf_token`)**

認証情報は、Fantiaサーバーに対して正規のユーザーとしてアクセスしていることを証明するために必要になります。

1.  PCのウェブブラウザ（Chrome推奨）でFantiaにログインします。
2.  **閲覧権限のあるいずれかの小説ページ**を開きます。
3.  `F12`キーを押して「開発者ツール」を開き、「**ネットワーク (Network)**」タブを選択します。
4.  フィルタ欄で「Fetch/XHR」をクリックします。
4.  `F5`キーを押してページを再読み込みします。
5.  リストに表示された通信の中から、`1234567` のような形式の名前を持つものをクリックし、リクエストURLが `https://fantia.jp/api/v1/posts/1234567` のようになっていることを確認します。
6.  右側に表示される詳細ウィンドウの「**ヘッダー (Headers)**」タブを下にスクロールし、「**リクエストヘッダー (Request Headers)**」セクションを探します。
7.  以下の2つの値を、`config.ini` にコピー＆ペーストします。
    *   **`cookie`**: `_session_id=...` などを含む、非常に長い行**全体**。
    *   **`x-csrf-token`**: ランダムな英数字からなるトークン文字列。

> **Note:** これらの認証情報は、時間経過や再ログインによって無効になる場合があります。プログラムが正常に動作しなくなった場合は、この手順に従って最新の情報を再取得・再設定してください。

### 3.2. `DL-links.txt` の設定

このファイルに、ダウンロード対象としたいファンクラブの**小説一覧ページのURL**を、1行に1つずつ記述します。

**例:**
```
https://fantia.jp/fanclubs/123456/posts
https://fantia.jp/fanclubs/234567/posts?tag=小説
https://fantia.jp/fanclubs/345678/posts?tag=%E5%B0%8F%E8%AA%AC
```
> **Tip:** `?tag=小説` や `?tag=%E5%B0%8F%E8%AA%AC` の部分は、そのファンクラブが小説に特定のタグを使用している場合に必要です。タグで絞り込まない場合は、`https://fantia.jp/fanclubs/123456/posts` のように、URLからタグ部分を削除してください。

## 4. 実行 (Usage)

すべての設定が完了したら、Fantia-novel-downloader_ja.pyをダブルクリックして実行するか、ターミナルまたはコマンドプロンプトで以下のコマンドを入力します。

```bash
python Fantia-novel-downloader_ja.py
```

プログラムが起動し、`DL-links.txt` に記載されたURLを順番に処理していきます。

## 5. 出力構造 (Output Structure)

実行後、`config.ini` で指定した `root_output_dir` （デフォルトでは `fantia_novels`）が生成され、その内部にファンクラブごとのフォルダが作成されます。

```
.
├── Fantia-novel-downloader_ja.py
├── config.ini
├── DL-links.txt
│
└── fantia_novels/
    ├── ファンクラブA (作者名A)/
    │   ├── 小説タイトル1.txt
    │   └── 小説タイトル2.txt
    │
    └── ファンクラブB (作者名B)/
        ├── 小説タイトル3.txt
        └── ...
```

## 6. トラブルシューティング (Troubleshooting)

*   **「ログインに失敗しています」というエラーが出る**:
    *   `config.ini` に設定した `cookie` が古いか、間違っています。上記「認証情報の取得方法」に従って、最新の値を再設定してください。
*   **投稿の取得でエラーが多発する**:
    *   `config.ini` の `x_csrf_token` が古い可能性があります。`cookie` と同様に、最新の値を再設定してください。
*   **特定のファンクラブの投稿が一件も見つからない**:
    *   `DL-links.txt` に記述したURLが正しいか確認してください。

## 7. ライセンス (License)

This project is licensed under the MIT License.
