import streamlit as st
import auth
import database as db
import datetime
import pandas as pd
import sqlite3

st.set_page_config(page_title="Softball Scorebook SaaS", layout="wide")

db.init_db()

# ------------------------------
#     🛠️ メンテナンス・設定 
# ------------------------------

# 作業時は True に書き換えて Push する

IS_MAINTENANCE = True

# git add main.py
# git commit -m "メンテナンスモード有効化"
# git push origin main
# cd softball-app
# git pull origin main

if IS_MAINTENANCE:

# マスター管理者だけはメンテナンス中でも入れるように設定
# ログイン済みの状態なら master1234 等のパスワードではなく session_state で判定

    if not st.session_state.get("is_master_admin", False):
        st.image("Core.cct_LOGO.png", width=300)
        st.error("### 🛠️ ただいまシステムメンテナンス中です")
        st.markdown("""
        ご不便をおかけしており申し訳ございません。  
        現在、新機能の追加およびデータベースの最適化作業を行っております。
        
        **【作業予定時間】** 2026年3月1日 22:50 〜 2026年3月2日 00:00  
        
        ※作業が完了次第、自動的にアクセス可能となります。
        """)
        
        # マスターログインだけは裏口として残しておく（動作確認用）
        with st.expander("管理者ログイン (作業用)"):
            m_key = st.text_input("Maintenance Key", type="password")
            if st.button("Enter"):
                if m_key == "master1234": 
                    st.session_state.is_master_admin = True
                    st.rerun()
        
        st.stop() 

# ------------------------------


# ■認証-----------------

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


# ■管理-----------------

if st.session_state.get("is_master_admin", False):
    st.sidebar.title("Master Menu")
    if st.sidebar.button("Exit Master Mode"):
        st.session_state.is_master_admin = False
        st.rerun()
    st.stop()


# ■閲覧-----------------

if "user_role" not in st.session_state: st.session_state.user_role = "guest"
if "username" not in st.session_state: st.session_state.username = "Guest" 
if "is_viewer_mode" not in st.session_state: st.session_state.is_viewer_mode = False
if "club_name" not in st.session_state: st.session_state.club_name = "Unknown Club" 
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


# ■menu-----------------

if st.session_state.get("is_viewer_mode", False):
    pages = {"ホーム": "home", "選手名鑑": "directory", "試合結果一覧": "history"}
else:
    pages = {
        "ホーム": "home", 
        "スケジュール": "scheduler", 
        "選手名鑑": "directory", 
        "選手個人分析": "profile", 
        "成績ランキング": "stats", 
        "試合結果一覧": "history"
    }
    
    if role in ["admin", "operator"]:
        pages["簡易スコア入力"] = "scorebook"
        pages["詳細スコア入力"] = "nomal_scorebook"        
        if plan_type == "premium":
            pages["分析スコア入力"] = "mobile_scorebook"            
    if role == "admin":
        pages["⚙️ 管理設定 (Admin)"] = "settings"

page_list = list(pages.keys())


# ■ボタン-----------------

if "main_nav" not in st.session_state:
    st.session_state.main_nav = page_list[0]

st.sidebar.title("メニュー")
selection = st.sidebar.radio("Go to", page_list, key="main_nav")


# ■DB管理-----------------

if role == "admin" and st.sidebar.checkbox("DB管理表示", value=False):
    st.sidebar.divider()
    try:
        with open("softball.db", "rb") as f:
            st.sidebar.download_button("DB全体バックアップ", f, "softball.db")
    except FileNotFoundError:
        st.sidebar.error("DBファイルが見つかりません")



# ■デバッグ-----------------

def check_sync_data():

    with sqlite3.connect("softball.db") as conn: 
        try:
            df = pd.read_sql("SELECT * FROM core_cct_logs ORDER BY id DESC LIMIT 5", conn)
            if df.empty:
                st.warning("同期成功のメッセージは出ましたが、テーブルの中身は空のようです。")
            else:
                st.write("最新の同期データ（5件）:", df)
        except Exception as e:
            st.error(f"テーブル読み込みエラー: {e}")
            st.info("まだ一度も同期に成功していないか、テーブルが作成されていない可能性があります。")


# ---------------------
# 　　ルーティング
# ---------------------

page_key = pages[selection]

if page_key != "mobile_scorebook":
    st.markdown(f"### {st.session_state.get('club_name')} / ようこそ")
    st.divider()

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
elif page_key == "nomal_scorebook":
    import nomal_scorebook; nomal_scorebook.show()
elif page_key == "mobile_scorebook":


# ■分析スコア入力（モバイルモード）の制御 ---
    
    st.session_state.is_standalone_mobile = False

    if "club_id" in st.session_state:
        st.session_state.authenticated = True

    import mobile_scorebook

    if hasattr(mobile_scorebook, "init_session_for_detailed_input"):
        mobile_scorebook.init_session_for_detailed_input()

    mobile_scorebook.show_mobile_ui()

elif page_key == "settings":
    import admin_settings; admin_settings.show()



# 20260226 Ver.1.0
