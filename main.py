import streamlit as st
import auth
import database as db
import datetime
import pandas as pd

# ページ設定
st.set_page_config(page_title="Softball Scorebook SaaS", layout="wide")

# DB初期化
db.init_db()

# --- 1. 認証チェック ---
if "club_id" not in st.session_state and not st.session_state.get("is_master_admin", False):
    st.image("Core.cct_LOGO.png", width=300)
    tab_login, tab_register, tab_master = st.tabs(["ユーザーログイン", "新規倶楽部登録", "🌐Master Access"])
    with tab_login: auth.login_club_ui()
    with tab_register: auth.register_club_ui()
    with tab_master:
        master_key = st.text_input("Master Password", type="password")
        if st.button("Master Login"):
            if master_key == "master1234":
                st.session_state.is_master_admin = True
                st.rerun()
    st.stop()

# --- 2. マスター管理画面 ---
if st.session_state.get("is_master_admin", False):
    st.sidebar.title("Master Menu")
    if st.sidebar.button("Exit Master Mode"):
        st.session_state.is_master_admin = False
        st.rerun()
    # (中略: マスター画面ロジック)
    st.stop()

# --- 3. アプリ本体ステート初期化 ---

if "user_role" not in st.session_state: st.session_state.user_role = "guest"
if "username" not in st.session_state: st.session_state.username = "Guest" # 👈 これを追加
if "is_viewer_mode" not in st.session_state: st.session_state.is_viewer_mode = False
if "club_name" not in st.session_state: st.session_state.club_name = "Unknown Club" # 👈 これも念のた

if not st.session_state.is_viewer_mode:
    auth.login_sidebar()
else:
    if st.sidebar.button("🚪 閲覧モードを終了"):
        st.session_state.clear()
        st.rerun()

role = st.session_state.get("user_role", "guest")
club_id = st.session_state.get("club_id")
plan_info = db.get_club_plan(club_id)
plan_type = plan_info.get('plan_type', 'free')

# --- 4. メニュー定義 ---
if st.session_state.is_viewer_mode:
    pages = {"ホーム": "home", "選手名鑑": "directory", "試合結果一覧": "history"}
else:
    pages = {"ホーム": "home", "スケジュール": "scheduler", "選手名鑑": "directory", "選手個人分析": "profile", "成績ランキング": "stats", "試合結果一覧": "history"}
    if role in ["admin", "operator"]:
        pages["スコア入力"] = "scorebook"
        if plan_type == "premium":
            pages["超詳細スコア入力"] = "mobile_scorebook"
    if role == "admin":
        pages["⚙️ 管理設定 (Admin)"] = "settings"

page_list = list(pages.keys())

# --- 💡【重要】メニュー選択の強力な固定ロジック ---
# key="main_nav" を使うことで、st.session_state.main_nav と radio が直結します
if "main_nav" not in st.session_state:
    st.session_state.main_nav = page_list[0]

st.sidebar.title("メニュー")
# セッション変数 'main_nav' と radio ボタンを同期
selection = st.sidebar.radio("Go to", page_list, key="main_nav")

# 管理者専用：DB管理
if role == "admin" and st.sidebar.checkbox("DB管理表示", value=False):
    st.sidebar.divider()
    try:
        with open("softball.db", "rb") as f:
            st.sidebar.download_button("DB全体バックアップ", f, "softball.db")
    except FileNotFoundError:
        st.sidebar.error("DBファイルが見つかりません")

# --- 5. ページルーティング ---
page_key = pages[selection]

# モバイルスコアブック以外では共通のヘッダーを表示
if page_key != "mobile_scorebook":
    st.markdown(f"### {st.session_state.get('club_name')} / ようこそ")
    st.divider()

# 各ページモジュールの呼び出し
if page_key == "home":
    import home; home.show()
elif page_key == "scheduler":
    import scheduler; scheduler.show()
elif page_key == "stats":
    import stats; stats.show()
elif page_key == "directory":
    import player_directory; player_directory.show()
elif page_key == "profile":
    import player_profile; player_profile.show()
elif page_key == "history":
    import game_history; game_history.show()
elif page_key == "scorebook":
    import scorebook; scorebook.show()
elif page_key == "mobile_scorebook":
    # --- 超詳細スコア入力（モバイルモード）の制御 ---
    
    # 1. オンラインモード（main.py経由）であることを明示
    st.session_state.is_standalone_mobile = False
    
    # 2. 認証状態の強制同期
    # main.pyでログイン済みであれば、mobile_scorebook側のガードをパスさせる
    if "club_id" in st.session_state:
        st.session_state.authenticated = True
    
    # 3. モジュールのインポートと初期化
    import mobile_scorebook
    
    # 詳細入力用のセッション初期化関数があれば実行
    if hasattr(mobile_scorebook, "init_session_for_detailed_input"):
        mobile_scorebook.init_session_for_detailed_input()
    
    # 4. 明示的なUI関数呼び出し（これによりロゴで止まる不具合を回避）
    mobile_scorebook.show_mobile_ui()

elif page_key == "settings":
    import admin_settings; admin_settings.show()