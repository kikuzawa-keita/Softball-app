import streamlit as st
import auth
import database as db
import datetime
import pandas as pd

# ページ設定
st.set_page_config(page_title="Softball Scorebook SaaS", layout="wide")

# DB初期化（テーブル作成・マイグレーション）
db.init_db()

# --- 1. 認証チェック ---
if "club_id" not in st.session_state and not st.session_state.get("is_master_admin", False):
    st.title("⚾ Softball Manager")
    # ログイン・新規登録・マスターアクセスのタブを生成
    tab_login, tab_register, tab_master = st.tabs(["倶楽部ログイン", "新規倶楽部登録", "System Master Access"])

    with tab_login:
        auth.login_club_ui()

    with tab_register:
        auth.register_club_ui()

    with tab_master:
        st.subheader("🌐 システムマスター認証")
        master_key = st.text_input("Master Password", type="password", key="master_input")
        if st.button("Master Login", key="master_btn"):
            if master_key == "master1234": 
                st.session_state.is_master_admin = True
                st.rerun()
            else:
                st.error("Invalid Key")
    st.stop()

# --- 2. マスター管理画面の表示ロジック ---
if st.session_state.get("is_master_admin", False):
    st.sidebar.title("Master Menu")
    if st.sidebar.button("Exit Master Mode"):
        st.session_state.is_master_admin = False
        st.rerun()

    st.header("🌐 システムマスター管理画面")
    st.warning("注意：ここでの削除操作は取り消せません。倶楽部に紐付く全データが削除されます。")
    
    all_clubs = db.get_all_clubs()
    st.subheader("登録済み倶楽部一覧")
    st.dataframe(all_clubs, use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.subheader("倶楽部の管理・削除")
    if not all_clubs.empty:
        col1, col2 = st.columns([3, 1])
        with col1:
            target_club = st.selectbox("管理対象の倶楽部を選択", all_clubs['name'].tolist())
            target_id = all_clubs[all_clubs['name'] == target_club]['id'].values[0]
        
        with col2:
            st.write("") 
            if st.button(f"{target_club} を完全に削除", type="primary"):
                db.delete_club_complete(target_id)
                st.success(f"倶楽部「{target_club}」を削除しました。")
                st.rerun()
    else:
        st.write("登録されている倶楽部はありません。")
    
    st.stop()

# --- 3. 以下、ログイン後のアプリ本体 ---

# セッション状態の初期化
if "user_role" not in st.session_state:
    st.session_state.user_role = "guest"
if "username" not in st.session_state:
    st.session_state.username = "Guest"
if "editing_game_id" not in st.session_state:
    st.session_state.editing_game_id = None

# サイドバー表示
auth.login_sidebar()

# ユーザー権限の取得
role = st.session_state.get("user_role", "guest")
username = st.session_state.get("username", "Guest")
club_name = st.session_state.get("club_name", "Unknown Club")
club_id = st.session_state.get("club_id")

# --- 4. プラン制限チェック ---
# ここでの判定ロジックは内部的な制御（メニュー表示等）に使う可能性があるため残しますが、
# 画面への st.error 表示は削除しました。
plan_info = db.get_club_plan(club_id)
current_year = datetime.datetime.now().year
game_count = db.get_yearly_game_count(club_id, current_year)
is_over_limit = (plan_info['plan_type'] == 'free' and game_count >= plan_info['max_games_yearly'])

# 疑似ログイン表示名決定
if "active_player" in st.session_state and st.session_state.active_player != "(未選択)":
    display_name = st.session_state.active_player
    status_label = f"🏃 選手：{display_name}"
else:
    display_name = st.session_state.username
    status_label = f"👤 ユーザー：{display_name}"

# 権限別のメニュー定義
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

# サイドバーナビゲーション
st.sidebar.caption(f"現在の倶楽部: **{club_name}**")
st.sidebar.divider()
st.sidebar.caption("現在の操作ユーザー")
st.sidebar.markdown(f"**{status_label}**") 
st.sidebar.divider()

st.sidebar.title("メニュー")
selection = st.sidebar.radio("Go to", list(pages.keys()))

# 管理者専用：バックアップダウンロード
if role == "admin" and st.sidebar.checkbox("DB管理表示", value=False):
    st.sidebar.divider()
    with open("softball.db", "rb") as f:
        st.sidebar.download_button("DB全体バックアップ", f, "softball.db")

# メインエリア共通ヘッダー
st.markdown(f"### {club_name} / ようこそ、{display_name} さん")

# --- 全体警告表示の削除 ---
# 全ページ共通の警告表示を削除しました。

st.divider()

# 各ページの読み込み
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