import streamlit as st
import database as db
import json
import pandas as pd
import sqlite3
import textwrap

def show():
    st.title("🗓️ 試合結果一覧")

    # 冒頭にこれを追加（セッションから安全に取得）
    role = st.session_state.get("user_role", "guest")
    username = st.session_state.get("username", "Guest")
    
    # 1. データ取得 (database.py の get_game_history を使用)
    history = db.get_game_history()
    if not history:
        st.info("試合データがありません。")
        return

    df = pd.DataFrame(history)
    
    # カラム名マッピング (database.py の JSONキー名に合わせる)
    mapping = {
        'date': '日付', 'opponent': '相手', 'name': '大会・試合名', 
        'my_team': '自チーム', 'total_my': '得点', 'total_opp': '失点', 
        'result': '結果', 'game_id': 'ID'
    }
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})

    # 欠損カラム補完
    for col in ['日付', '結果', '得点', '失点', '相手', '自チーム']:
        if col not in df.columns: 
            df[col] = "未設定" if col in ['日付', '結果', '相手', '自チーム'] else 0

    # 日付処理
    df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
    df = df.dropna(subset=['日付']).sort_values("日付", ascending=False)
    df['年度'] = df['日付'].dt.year

    # --- 2. フィルタリング ---
    st.sidebar.header("表示フィルタ")
    sel_team = st.sidebar.selectbox("チームで絞り込み", ["すべて"] + sorted(df['自チーム'].unique().tolist()))
    sel_year = st.sidebar.selectbox("年度で絞り込み", ["すべて"] + sorted(df['年度'].unique().astype(str).tolist(), reverse=True))
    
    filtered_df = df.copy()
    if sel_team != "すべて": 
        filtered_df = filtered_df[filtered_df['自チーム'] == sel_team]
    if sel_year != "すべて": 
        filtered_df = filtered_df[filtered_df['年度'] == int(sel_year)]

    st.divider()

    # --- 3. 試合リスト表示 ---
    for _, row in filtered_df.iterrows():
        g_id = row['ID']
        
        # 投手成績から勝敗フラグがあるか確認
        with sqlite3.connect('softball.db') as conn:
            p_check = pd.read_sql("SELECT win, loss FROM scorebook_pitching WHERE game_id = ?", conn, params=(g_id,))
        
        has_win = (p_check['win'] == 1).any() if not p_check.empty else False
        has_loss = (p_check['loss'] == 1).any() if not p_check.empty else False

        # 勝敗判定
        my_score = int(row['得点'])
        opp_score = int(row['失点'])

        if my_score > opp_score or has_win:
            bg_color = "#e6f3ff"
            border_color = "#004085"
            icon = "○"
        elif my_score < opp_score or has_loss:
            bg_color = "#f8d7da"
            border_color = "#721c24"
            icon = "●"
        else:
            bg_color = "#fff3cd"
            border_color = "#856404"
            icon = "‐"

        header_html = f"""
            <div style="background-color: {bg_color}; padding: 12px 15px; border-radius: 5px; 
                 border-left: 8px solid {border_color}; margin-bottom: 5px; display: flex; align-items: center;">
                <div style="color: {border_color}; font-size: 0.95rem; width: 100%;">
                    <span style="font-weight: bold; margin-right: 15px;">{icon} {row['日付'].strftime('%Y/%m/%d')}</span>
                    <span style="font-size: 1.1rem;">
                        <b style="text-decoration: underline;">{row['自チーム']}</b> {row['得点']} - {row['失点']} {row['相手']}
                    </span>
                    <span style="margin-left: 20px; color: #555; font-size: 0.85rem;">🏆 {row.get('大会・試合名', '未設定')}</span>
                </div>
            </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)

        with st.expander("詳細データ（スコア・成績・戦評）"):
            # 削除ボタンのみ配置 (Adminのみ)
            if role == "admin":
                if st.button("🗑️ 試合データを削除", key=f"del_{g_id}", type="secondary"):
                    @st.dialog("削除の確認")
                    def confirm_delete(gid):
                        st.warning("この試合データを完全に削除しますか？この操作は取り消せません。")
                        if st.button("はい、削除します", type="primary", use_container_width=True, key=f"conf_del_{gid}"):
                            with sqlite3.connect('softball.db') as conn:
                                # database.pyの構成に合わせ、関連テーブルから削除
                                conn.execute("DELETE FROM scorebook_batting WHERE game_id = ?", (gid,))
                                conn.execute("DELETE FROM scorebook_pitching WHERE game_id = ?", (gid,))
                                # 戦評も削除
                                conn.execute("DELETE FROM game_comments WHERE game_id = ?", (gid,))
                                conn.execute("DELETE FROM games WHERE id = ?", (gid,))
                                conn.commit()
                            db.add_activity_log(username, "DELETE_GAME", f"Deleted GameID: {gid}")
                            st.success("試合データを削除しました。")
                            st.rerun()
                    confirm_delete(g_id)

            # スコア表
            try:
                raw_scores = row.get('inning_scores', '{"my":[], "opp":[]}')
                scores = json.loads(raw_scores) if isinstance(raw_scores, str) else raw_scores
                
                my_s, opp_s = scores.get('my', []), scores.get('opp', [])
                max_inns = max(len(my_s), len(opp_s), 1)
                sb_dict = {"チーム": [row['自チーム'], row['相手']]}
                for i in range(max_inns):
                    sb_dict[f"{i+1}"] = [my_s[i] if i < len(my_s) else "-", opp_s[i] if i < len(opp_s) else "-"]
                sb_dict["計"] = [row['得点'], row['失点']]
                st.table(pd.DataFrame(sb_dict).set_index("チーム"))
            except Exception:
                st.info(f"スコア: {row['得点']} - {row['失点']}")

            # 成績詳細・戦評タブ
            t1, t2, t3 = st.tabs(["⚾ 打撃成績", "🥎 投手成績", "📝 戦評"])
            with t1:
                with sqlite3.connect('softball.db') as conn:
                    b_df_raw = pd.read_sql("SELECT player_name, innings, summary FROM scorebook_batting WHERE game_id = ?", conn, params=(g_id,))
                
                if not b_df_raw.empty:
                    rows_data = []
                    for _, db_r in b_df_raw.iterrows():
                        # JSONを安全にロード
                        try:
                            inns_list = json.loads(db_r['innings']) if isinstance(db_r['innings'], str) else db_r['innings']
                            summ_dict = json.loads(db_r['summary']) if isinstance(db_r['summary'], str) else db_r['summary']
                        except:
                            inns_list = []
                            summ_dict = {}

                        d = {"選手名": db_r['player_name']}
                        
                        # 各打席の結果を展開
                        for i, inn in enumerate(inns_list):
                            d[f"{i+1}打席"] = inn.get('res', '---')
                        
                        # サマリーを追加
                        d.update({
                            "打点": summ_dict.get('rbi', 0),
                            "盗塁": summ_dict.get('sb', 0),
                            "得点": summ_dict.get('run', 0),
                            "失策": summ_dict.get('err', 0)
                        })
                        rows_data.append(d)
                    
                    # リストからDataFrameを作成
                    display_b_df = pd.DataFrame(rows_data)
                    if not display_b_df.empty:
                        st.dataframe(display_b_df.set_index("選手名"), use_container_width=True)
                else:
                    st.caption("打撃データなし")

            with t2:
                with sqlite3.connect('softball.db') as conn:
                     p_display = pd.read_sql("""
                        SELECT player_name as 選手名, win as 勝, loss as 負, ip as 投球回, 
                               np as 球数, h as 被安, so as 奪三振, r as 失点 
                        FROM scorebook_pitching WHERE game_id = ?
                    """, conn, params=(g_id,))
                if not p_display.empty:
                    st.dataframe(p_display.set_index("選手名"), use_container_width=True)
                else:
                    st.caption("投手データなし")

            with t3:
                comment = db.get_game_comment(g_id)
                if comment:
                    # 空行維持の処理
                    processed_comment = comment.replace('\n\n', '\n&nbsp;\n')
                    st.markdown(f"""
<div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; border: 1px solid #ddd; min-height: 100px; white-space: pre-wrap; line-height: 1.6; color: #333;">
{processed_comment}
</div>
""", unsafe_allow_html=True)
                else:
                    st.info("この試合の戦評はまだ登録されていません。")

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)