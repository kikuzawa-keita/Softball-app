import streamlit as st
import database as db
import streamlit.components.v1 as components  # コンポーネント機能を追加
from datetime import datetime

def show():
    # --- Club ID 取得 ---
    club_id = st.session_state.club_id

    # --- 1. 管理者設定によるカスタマイズ情報の取得 ---
    custom_data = db.get_club_customization(club_id)

    # --- 表示名の動的決定 ---
    if "active_player" in st.session_state and st.session_state.active_player != "(未選択)":
        selected_player = st.session_state.active_player
        display_name = selected_player
    else:
        selected_player = "(未選択)"
        display_name = st.session_state.username

    # --- デザイン設定 ---
    st.markdown("""
        <style>
        .team-tag-home {
            padding: 2px 8px; border-radius: 4px;
            font-size: 0.7rem; font-weight: bold;
            color: white; margin-right: 5px;
            display: inline-block;
            margin-bottom: 5px;
        }
        .insta-container {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 10px;
            background: white;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- 2. 挨拶とメインコンテンツ ---
    
    col_main, col_side = st.columns([2, 1])
    
    with col_main:
        st.markdown(f"### {custom_data['welcome_message']}")
        
        # メンバーへのお知らせ
        if custom_data['member_announcement'] and custom_data['member_announcement'] != "（メンバーへのお知らせはまだありません）":
            with st.container(border=True):
                st.markdown("##### 📢 倶楽部からのお知らせ")
                st.info(custom_data['member_announcement'])

    with col_side:
        # Instagramセクション
        if custom_data.get('instagram_url'):
            st.markdown("##### 📸 Official Instagram")
            
            # 埋め込みが拒否される場合の代替案：リッチなバナー風ボタン
            st.markdown(
                f"""
                <a href="{custom_data['instagram_url']}" target="_blank" style="text-decoration: none;">
                    <div style="background: linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%); 
                                padding: 20px; border-radius: 10px; text-align: center; color: white; font-weight: bold;">
                        Instagramで最新の活動を見る<br>
                    </div>
                </a>
                """, 
                unsafe_allow_html=True
            )

    # チームカラー設定の取得
    team_colors = {name: color for name, color in db.get_all_teams_with_colors(club_id)}

    # --- 直近のスケジュール表示 ---
    st.subheader("📅 直近のスケジュール")
    
    all_events = db.get_all_events(club_id)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    def parse_event_home(ev):
        raw_title = ev[2] if len(ev) > 2 else ""
        extracted_teams = []
        clean_title = raw_title
        if raw_title.startswith("["):
            parts = raw_title.split("] ", 1)
            if len(parts) > 1:
                extracted_teams = [t.strip() for t in parts[0][1:].split(",")]
                clean_title = parts[1]
        return list(ev) + [extracted_teams, clean_title]

    parsed_events = [parse_event_home(e) for e in all_events]
    upcoming_events = sorted([e for e in parsed_events if e[1] >= today_str], key=lambda x: x[1])[:3]

    if upcoming_events:
        cols = st.columns(3)
        for i, event in enumerate(upcoming_events):
            ev_id, ev_date, _, ev_cat, ev_loc, ev_memo, ev_teams, ev_title = event
            
            expander_key = f"expander_ev_{ev_id}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False

            with cols[i]:
                with st.container(border=True):
                    display_date = ev_date[5:].replace("-", "/")
                    st.markdown(f"#### {display_date}")
                    
                    if ev_teams:
                        badge_html = "".join([
                            f'<span class="team-tag-home" style="background-color:{team_colors.get(t, "#6c757d")}">{t}</span>' 
                            for t in ev_teams
                        ])
                        st.markdown(badge_html, unsafe_allow_html=True)
                    else:
                        st.caption("チーム設定なし")

                    st.caption(f"[{ev_cat}]")
                    st.markdown(f"**{ev_title}**")
                    if ev_loc:
                        st.markdown(f"📍 {ev_loc}")
                    
                    if st.button("詳細・出欠回答", key=f"btn_ev_{ev_id}", use_container_width=True):
                        st.session_state[expander_key] = not st.session_state[expander_key]

                if st.session_state[expander_key]:
                    with st.container(border=True):
                        if selected_player == "(未選択)":
                            st.error("👈 操作プレイヤーを選択してください。")
                        else:
                            st.caption(f"📢 {selected_player} さんの出欠入力")
                            attendance = db.get_attendance_for_event(ev_id, club_id)
                            current_status = attendance.get(selected_player, "未回答")
                            
                            options = ["出席", "欠席", "保留", "未回答"]
                            try: def_idx = options.index(current_status)
                            except ValueError: def_idx = 3
                                
                            new_status = st.segmented_control(
                                "状況", options, selection_mode="single",
                                default=options[def_idx], key=f"status_home_{ev_id}"
                            )
                            
                            if st.button("更新", key=f"upd_home_{ev_id}", type="primary", use_container_width=True):
                                if new_status:
                                    db.update_attendance(ev_id, selected_player, new_status, club_id)
                                    db.add_activity_log(st.session_state.username, "ATTENDANCE_UPDATE", f"{selected_player}: {ev_title} -> {new_status}", club_id)
                                    st.success(f"保存しました")
                                    st.session_state[expander_key] = False
                                    st.rerun()

                        if ev_memo:
                            st.info(f"メモ: {ev_memo}")
    else:
        st.write("現在、予定されているイベントはありません。")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("権限", st.session_state.user_role)
    with col2:
        st.markdown("##### 📝 最近の活動")
        logs = db.get_activity_logs(club_id, limit=3)
        if logs:
            for row in logs:
                st.caption(f"{row['timestamp']} - {row['username']}")
                st.write(f"{row['action']}: {row['details']}")
        else:
            st.write("活動ログはありません。")