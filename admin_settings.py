import streamlit as st
import database as db

def show():
    # --- 0. ログインチェックと club_id 取得 ---
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("倶楽部セッションが見つかりません。ログインし直してください。")
        return

    st.title("⚙️ 管理設定パネル")
    
    # 権限チェック
    if st.session_state.get("user_role") != "admin":
        st.error("このページを表示する権限がありません。")
        return

    # 機能を3つのタブに分離
    tab1, tab2, tab3 = st.tabs(["🏃 チーム管理", "👥 ユーザー管理", "📜 操作ログ"])

    # --- TAB1: チーム管理 (新規追加・編集・削除) ---
    with tab1:
        st.subheader("チーム編成・カラー管理")
        with st.container(border=True):
            st.markdown("#### ➕ 新規チームの設立")
            col_name, col_color = st.columns([2, 1])
            with col_name:
                new_team = st.text_input("チーム名を入力", placeholder="例：シニアチーム", key="new_team_input")
            with col_color:
                new_color = st.color_picker("カラーを選択", "#3498db", key="new_team_color")
            
            if st.button("チームを新設する", type="primary", use_container_width=True):
                if new_team:
                    # club_id を指定して追加
                    if db.add_team_master(new_team, new_color, club_id=club_id):
                        st.success(f"チーム「{new_team}」を新設しました！")
                        st.rerun()
                    else:
                        st.error("登録済みの名前か、無効な入力です。")

        st.markdown("---")
        st.markdown("#### 📋 登録済みチームの管理")
        # club_id に紐づくチームのみ取得
        teams_data = db.get_all_teams_with_colors(club_id=club_id)
        
        if not teams_data:
            st.info("登録されたチームはありません。")
        else:
            for team_info in teams_data:
                name, color = team_info[0], team_info[1]
                with st.container(border=True):
                    cp, ci, ce, ca = st.columns([0.4, 1.5, 1.2, 1.2])
                    with cp:
                        st.markdown(f'<div style="background-color:{color}; width:35px; height:35px; border-radius:5px; border:1px solid #ddd; margin-top:10px;"></div>', unsafe_allow_html=True)
                    with ci:
                        st.markdown(f"**{name}**")
                        st.caption(f"現在の色: {color}")
                    with ce:
                        changed_color = st.color_picker("色変更", color, key=f"cp_{name}", label_visibility="collapsed")
                    with ca:
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("更新", key=f"upd_{name}"):
                                # club_id を指定して更新
                                db.update_team_color(name, changed_color, club_id=club_id)
                                st.toast(f"{name}の色を更新しました")
                                st.rerun()
                        with c2:
                            if st.button("削除", key=f"del_{name}"):
                                # club_id を指定して削除
                                db.delete_team(name, club_id=club_id)
                                st.rerun()

    # --- TAB2: ユーザー管理 ---
    with tab2:
        st.subheader(f"👥 {st.session_state.get('club_name', '自倶楽部')} のユーザー一覧")
        # club_id に紐づくユーザーのみ表示
        users = db.get_all_users(club_id=club_id)
        st.dataframe(users, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("新規ユーザー作成")
        c1, c2, c3 = st.columns(3)
        new_u = c1.text_input("ユーザー名", key="admin_new_u")
        new_p = c2.text_input("パスワード", type="password", key="admin_new_p")
        new_r = c3.selectbox("権限", ["admin", "operator"], key="admin_new_r")
        
        if st.button("ユーザー追加", use_container_width=True):
            if new_u and new_p:
                # club_id を紐づけてユーザー作成
                if db.create_user(new_u, new_p, new_r, club_id=club_id):
                    st.success(f"ユーザー {new_u} を作成しました")
                    db.add_activity_log(st.session_state.username, "CREATE_USER", f"New: {new_u} ({new_r})", club_id=club_id)
                    st.rerun()
                else:
                    st.error("ユーザー名が重複しているか、作成に失敗しました")
            else:
                st.warning("全項目入力してください")
        
        st.divider()
        st.subheader("ユーザー削除")
        if not users.empty:
            target_list = users['username'].tolist()
            del_target = st.selectbox("削除するユーザーを選択", target_list)
            if st.button("削除実行", type="primary"):
                # admin (自分自身やシステムの初期admin) の削除防止は db側でもガードが必要
                if del_target == st.session_state.username:
                    st.error("自分自身は削除できません")
                elif del_target == "admin" and club_id == "ADMIN_CLUB": # 特権管理者の場合
                    st.error("初期管理者は削除できません")
                else:
                    db.delete_user(del_target, club_id=club_id)
                    db.add_activity_log(st.session_state.username, "DELETE_USER", f"Deleted: {del_target}", club_id=club_id)
                    st.success(f"{del_target} を削除しました")
                    st.rerun()
        else:
            st.info("削除できるユーザーがいません")

    # --- TAB3: 操作ログ ---
    with tab3:
        st.subheader("📜 システム操作ログ (最新50件)")
        if st.button("ログを最新に更新"):
            st.rerun()
        
        # club_id に紐づくログのみ取得
        logs = db.get_activity_logs(club_id=club_id)
        if not logs.empty:
            st.dataframe(logs, use_container_width=True, hide_index=True)
        else:
            st.info("操作ログはありません。")