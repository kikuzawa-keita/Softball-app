import streamlit as st
import database as db
import json
import pandas as pd
import sqlite3

def delete_game_data(game_id, club_id):
    """指定された試合のデータをすべてのテーブルから完全に削除する"""
    try:
        with sqlite3.connect('softball.db') as conn:
            c = conn.cursor()
            # 関連するすべてのテーブルから削除
            tables = [
                "games", 
                "scorebook_batting", 
                "scorebook_pitching", 
                "super_detailed_at_bats"
            ]
            for table in tables:
                # gamesテーブルだけカラム名が id なので分岐
                id_col = "id" if table == "games" else "game_id"
                c.execute(f"DELETE FROM {table} WHERE {id_col} = ? AND club_id = ?", (str(game_id), str(club_id)))
            
            conn.commit()
        return True
    except Exception as e:
        st.error(f"削除エラー: {e}")
        return False

def show():
    # --- 0. ログインチェックと club_id 取得 ---
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("倶楽部セッションが見つかりません。ログインし直してください。")
        return

    st.title("🗓️ 試合結果一覧")

    role = st.session_state.get("user_role", "guest")
    
    # 1. データ取得
    history = db.get_game_history(club_id)
    
    # 詳細データテーブル（super_detailed_at_bats）にのみ存在する「孤立したデータ」も拾う
    with sqlite3.connect('softball.db') as conn:
        orphans = pd.read_sql("""
            SELECT DISTINCT game_id as id, SUBSTR(game_id, 1, 10) as date, 
            'モバイル同期' as opponent, '未設定' as my_team, 0 as total_my, 0 as total_opp 
            FROM super_detailed_at_bats 
            WHERE club_id = ? AND game_id NOT IN (SELECT id FROM games)
        """, conn, params=(str(club_id),))

    if not history and orphans.empty:
        st.info("表示できる試合データがありません。")
        return

    df = pd.DataFrame(history) if history else pd.DataFrame()
    if not orphans.empty:
        df = pd.concat([df, orphans], ignore_index=True).drop_duplicates(subset=['id'])

    # カラム名マッピング
    mapping = {'date': '日付', 'opponent': '相手', 'name': '大会・試合名', 'my_team': '自チーム', 'total_my': '得点', 'total_opp': '失点', 'result': '結果', 'id': 'ID'}
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})

    # データ整形
    df['日付'] = pd.to_datetime(df['日付'], errors='coerce')
    df = df.dropna(subset=['日付']).sort_values("日付", ascending=False)
    df['年度'] = df['日付'].dt.year

    # --- 2. フィルタリング ---
    st.sidebar.header("表示フィルタ")
    sel_team = st.sidebar.selectbox("チームで絞り込み", ["すべて"] + sorted(df['自チーム'].unique().tolist()))
    sel_year = st.sidebar.selectbox("年度で絞り込み", ["すべて"] + sorted(df['年度'].unique().astype(str).tolist(), reverse=True))
    
    filtered_df = df.copy()
    if sel_team != "すべて": filtered_df = filtered_df[filtered_df['自チーム'] == sel_team]
    if sel_year != "すべて": filtered_df = filtered_df[filtered_df['年度'] == int(sel_year)]

    st.divider()

    # --- 3. 試合リスト表示 ---
    for _, row in filtered_df.iterrows():
        g_id = row['ID']
        
        with sqlite3.connect('softball.db') as conn:
            p_check = pd.read_sql("SELECT win, loss FROM scorebook_pitching WHERE game_id = ? AND club_id = ?", conn, params=(str(g_id), str(club_id)))
        
        has_win = (p_check['win'] == 1).any() if not p_check.empty else False
        has_loss = (p_check['loss'] == 1).any() if not p_check.empty else False
        my_score, opp_score = int(row.get('得点', 0)), int(row.get('失点', 0))

        # 勝敗による色分け表示
        if my_score > opp_score or has_win:
            bg_color = "#e6f3ff"; border_color = "#004085"; icon = "○"
        elif my_score < opp_score or has_loss:
            bg_color = "#f8d7da"; border_color = "#721c24"; icon = "●"
        else:
            bg_color = "#fff3cd"; border_color = "#856404"; icon = "‐"

        header_html = f"""
            <div style="background-color: {bg_color}; padding: 12px 15px; border-radius: 5px; 
                 border-left: 8px solid {border_color}; margin-bottom: 5px; display: flex; align-items: center;">
                <div style="color: {border_color}; font-size: 0.95rem; width: 100%;">
                    <span style="font-weight: bold; margin-right: 15px;">{icon} {row['日付'].strftime('%Y/%m/%d')}</span>
                    <span style="font-size: 1.1rem;">
                        <b style="text-decoration: underline;">{row['自チーム']}</b> {my_score} - {opp_score} {row['相手']}
                    </span>
                </div>
            </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)

        with st.expander("詳細データ（スコア・成績・戦評）"):
            # スコア表
            try:
                raw_scores = row.get('inning_scores', '{"my":[], "opp":[]}')
                scores = json.loads(raw_scores) if isinstance(raw_scores, str) else raw_scores
                my_s, opp_s = scores.get('my', []), scores.get('opp', [])
                max_inns = max(len(my_s), len(opp_s), 1)
                sb_dict = {"チーム": [row['自チーム'], row['相手']]}
                for i in range(max_inns):
                    sb_dict[f"{i+1}"] = [my_s[i] if i < len(my_s) else "-", opp_s[i] if i < len(opp_s) else "-"]
                sb_dict["計"] = [my_score, opp_score]
                st.table(pd.DataFrame(sb_dict).set_index("チーム"))
            except:
                st.info(f"スコア: {my_score} - {opp_score}")

            # 成績タブ
            t1, t2, t3, t4 = st.tabs(["⚾ 打撃成績", "🥎 投手成績", "📝 戦評", "⚠️ 管理"])
            
            with t1:
                with sqlite3.connect('softball.db') as conn:
                    b_df_raw = pd.read_sql("SELECT player_name, innings, summary FROM scorebook_batting WHERE game_id = ? AND club_id = ?", conn, params=(str(g_id), str(club_id)))
                    if not b_df_raw.empty:
                        rows_data = []
                        for _, db_r in b_df_raw.iterrows():
                            try:
                                d = {"選手名": db_r['player_name']}
                                inns = json.loads(db_r['innings']) if isinstance(db_r['innings'], str) else []
                                summ = json.loads(db_r['summary']) if isinstance(db_r['summary'], str) else {}
                                for i, inn in enumerate(inns): d[f"{i+1}打席"] = inn.get('res', '---')
                                d.update({"打点": summ.get('rbi', 0), "安打": summ.get('h', 0), "得点": summ.get('run', 0), "失策": summ.get('err', 0)})
                                rows_data.append(d)
                            except: continue
                        st.dataframe(pd.DataFrame(rows_data).set_index("選手名"), width='stretch')
                    
                    detailed_check = pd.read_sql("SELECT at_bat_no, inning, batter_name, result, hit_direction FROM super_detailed_at_bats WHERE game_id = ? AND club_id = ? ORDER BY at_bat_no", conn, params=(str(g_id), str(club_id)))
                    if not detailed_check.empty:
                        with st.expander("📲 モバイル同期の全打席詳細を表示"):
                            st.dataframe(detailed_check.set_index("at_bat_no"), width='stretch')

            with t2:
                with sqlite3.connect('softball.db') as conn:
                    p_display = pd.read_sql("SELECT player_name as 選手名, win as 勝, loss as 負, ip as 投球回, np as 球数, h as 被安, so as 奪三振, r as 失点 FROM scorebook_pitching WHERE game_id = ? AND club_id = ?", conn, params=(str(g_id), str(club_id)))
                    if not p_display.empty:
                        st.dataframe(p_display.set_index("選手名"), width='stretch')
                    else:
                        st.caption("投手データなし")

            with t3:
                comment = db.get_game_comment(g_id, club_id)
                st.write(comment if comment else "戦評なし")

            with t4:
                st.warning("この操作は取り消せません。この試合に関連するすべての成績と詳細データが削除されます。")
                if st.button(f"🗑️ 試合データを完全に削除", key=f"del_{g_id}", type="secondary", width='stretch'):
                    if delete_game_data(g_id, club_id):
                        st.success("削除しました。画面を更新します...")
                        st.rerun()

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)