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
    st.image("Core.cct_LOGO.png", width=300)
    
    # ログイン・登録・マスターアクセスの3タブ構成
    tab_login, tab_register, tab_master = st.tabs([
        "ユーザーログイン", "新規倶楽部登録（登録無料）", "🌐System Master Access"
    ])

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
    
    # 改修ポイント: 新しい関数を使用して指定された6項目を表示
    # 取得項目: ID \ ログインID \ ログインパス \ 正式名称 \ 作成日 \ Plan_type
    all_clubs = db.get_all_clubs_for_master()
    
    st.subheader("登録済み倶楽部一覧")
    if not all_clubs.empty:
        # 列名を分かりやすく表示
        display_df = all_clubs.rename(columns={
            "id": "ID",
            "login_id": "ログインID",
            "raw_password": "ログインパス",
            "display_name": "正式名称",
            "created_at": "作成日",
            "plan_type": "Plan_type"
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("登録されている倶楽部はありません。")
    
    st.divider()
    
    st.subheader("倶楽部の管理・プラン変更")
    if not all_clubs.empty:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            # 選択肢は「正式名称 (ログインID)」の形式にして識別しやすくする
            club_options = [f"{row['display_name']} ({row['login_id']})" for _, row in all_clubs.iterrows()]
            selected_option = st.selectbox("管理対象の倶楽部を選択", club_options)
            
            # 選択された情報から元データを逆引き
            idx = club_options.index(selected_option)
            target_info = all_clubs.iloc[idx]
            target_id = int(target_info['id'])
            target_name = target_info['display_name']
            current_plan = target_info['plan_type']
        
        with col2:
            new_plan = st.selectbox(
                f"プラン変更 ({current_plan})",
                ["free", "standard", "premium"],
                index=["free", "standard", "premium"].index(current_plan) if current_plan in ["free", "standard", "premium"] else 0
            )
            if st.button(f"{target_name} のプランを更新"):
                db.update_club_plan(target_id, new_plan)
                st.success(f"プランを {new_plan} に変更しました。")
                st.rerun()
        
        with col3:
            st.write("") 
            if st.button(f"{target_name} を完全に削除", type="primary"):
                db.delete_club_complete(target_id)
                st.success(f"倶楽部「{target_name}」を削除しました。")
                st.rerun()
    else:
        st.write("登録されている倶楽部はありません。")
    
    st.stop()

# --- 3. 以下、ログイン後のアプリ本体 ---
# (以下、変更なしのため省略。元のロジックをそのまま維持します)

# セッション状態の初期化
if "user_role" not in st.session_state:
    st.session_state.user_role = "guest"
if "username" not in st.session_state:
    st.session_state.username = "Guest"
if "editing_game_id" not in st.session_state:
    st.session_state.editing_game_id = None
if "is_viewer_mode" not in st.session_state:
    st.session_state.is_viewer_mode = False

# サイドバー表示
if not st.session_state.is_viewer_mode:
    auth.login_sidebar()
else:
    if st.sidebar.button("🚪 閲覧モードを終了"):
        st.session_state.clear()
        st.rerun()

# ユーザー権限・情報の取得
role = st.session_state.get("user_role", "guest")
username = st.session_state.get("username", "Guest")
# club_name は、DB側の display_name (正式名称) が入ることを想定
club_name = st.session_state.get("club_name", "Unknown Club")
club_id = st.session_state.get("club_id")

# プラン制限チェック
plan_info = db.get_club_plan(club_id)
current_year = datetime.datetime.now().year
game_count = db.get_yearly_game_count(club_id, current_year)
is_over_limit = (plan_info['plan_type'] == 'free' and game_count >= plan_info['max_games_yearly'])

# 表示名決定
if "active_player" in st.session_state and st.session_state.active_player != "(未選択)":
    display_name = st.session_state.active_player
    status_label = f"🏃 選手：{display_name}"
else:
    display_name = st.session_state.username
    status_label = f"👤 ユーザー：{display_name}"

# メニュー定義
if st.session_state.is_viewer_mode:
    pages = {
        "ホーム": "home",
        "選手名鑑": "directory",
        "試合結果一覧": "history"
    }
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
        pages["スコア入力(operator)"] = "scorebook"
    if role == "admin":
        pages["管理設定 (Admin)"] = "settings"

# サイドバーナビゲーション
st.sidebar.caption(f"現在の倶楽部: **{club_name}**")
if st.session_state.is_viewer_mode:
    st.sidebar.warning("⚠️ 閲覧モードでアクセス中")
st.sidebar.divider()
st.sidebar.caption("現在の操作ユーザー")
st.sidebar.markdown(f"**{status_label}**") 
st.sidebar.divider()

st.sidebar.title("メニュー")
selection = st.sidebar.radio("Go to", list(pages.keys()))

# 管理者専用：バックアップダウンロード
if role == "admin" and st.sidebar.checkbox("DB管理表示", value=False):
    st.sidebar.divider()
    try:
        with open("softball.db", "rb") as f:
            st.sidebar.download_button("DB全体バックアップ", f, "softball.db")
    except FileNotFoundError:
        st.sidebar.error("DBファイルが見つかりません")

# メインエリア共通ヘッダー
st.markdown(f"### {club_name} / ようこそ、{display_name} さん")
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