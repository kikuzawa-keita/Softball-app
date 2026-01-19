import streamlit as st
import auth
import database as db
import datetime

# ページ設定
st.set_page_config(page_title="Softball Scorebook", layout="wide")

# セッション状態の初期化
if "user_role" not in st.session_state:
    st.session_state.user_role = "guest"
if "username" not in st.session_state:
    st.session_state.username = "Guest"
if "editing_game_id" not in st.session_state:
    st.session_state.editing_game_id = None

# --- 初期化 ---
db.init_db()      # データ用DB
db.init_auth_db() # 認証用DB

# ログインサイドバー表示
auth.login_sidebar()

# ユーザー権限の取得
role = st.session_state.get("user_role", "guest")

# --- 疑似ログイン（選手選択）の表示名決定 ---
if "active_player" in st.session_state and st.session_state.active_player != "(未選択)":
    display_name = st.session_state.active_player
    status_label = f"🏃 選手：{display_name}"
else:
    display_name = st.session_state.username
    status_label = f"👤 ユーザー：{display_name}"

# --- 権限別のメニュー定義 ---
pages = {
    "ホーム": "home",
    "スケジュール": "scheduler",
    "選手名鑑": "directory",
    "選手個人分析": "profile",
    "成績ランキング": "stats",
    "試合結果一覧": "history"
}

if role in ["admin", "operator"]:
    pages["スコア入力(operator)"] = "scorebook"

if role == "admin":
    pages["管理設定 (Admin)"] = "settings"

# --- サイドバーナビゲーション ---
st.sidebar.divider()
st.sidebar.caption("現在の操作ユーザー")
st.sidebar.markdown(f"**{status_label}**") # サイドバーに常時表示
st.sidebar.divider()

st.sidebar.title("メニュー")
selection = st.sidebar.radio("Go to", list(pages.keys()))

# --- 管理者専用：バックアップダウンロードボタンの追加 ---
if role == "admin":
    st.sidebar.divider()
    st.sidebar.subheader("⚙️ 管理者ツール")
    try:
        with open("softball.db", "rb") as f:
            db_binary = f.read()
        
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        st.sidebar.download_button(
            label="💾 DBバックアップを保存",
            data=db_binary,
            file_name=f"softball_backup_{now}.db",
            mime="application/octet-stream",
            help="現在のデータベースファイルをダウンロードして手元に保存します。"
        )
    except Exception as e:
        st.sidebar.error("バックアップファイルの準備に失敗しました。")

# --- メインエリア共通ヘッダー ---
# すべてのページの上部に「ようこそ」を表示
st.markdown(f"### ようこそ、{display_name} さん")
st.divider()

# --- 各ページの読み込み ---
page_key = pages[selection]

if page_key == "home":
    import home
    home.show()
elif page_key == "scheduler":
    import scheduler
    scheduler.show()
elif page_key == "stats":
    import stats
    stats.show()
elif page_key == "directory":
    import player_directory
    player_directory.show()
elif page_key == "profile":
    import player_profile
    player_profile.show()
elif page_key == "history":
    import game_history
    game_history.show()
elif page_key == "scorebook":
    if role not in ["admin", "operator"]:
        st.error("権限がありません")
    else:
        import scorebook
        scorebook.show()
elif page_key == "settings":
    if role != "admin":
        st.error("権限がありません")
    else:
        import admin_settings
        admin_settings.show()