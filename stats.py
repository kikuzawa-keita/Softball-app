import streamlit as st
import pandas as pd
import database as db 

def show():
    st.title("🏆 チーム個人成績ランキング")

    role = st.session_state.get("user_role", "guest")
    username = st.session_state.get("username", "Guest")
    
    # --- 1. フィルタデータの準備 ---
    history = db.get_game_history()
    years = ["すべて"]
    if history:
        extracted_years = sorted(list(set([str(g.get('date', ''))[:4] for g in history if g.get('date')])), reverse=True)
        years.extend(extracted_years)

    all_teams = db.get_all_teams_in_order()
    
    # --- 2. サイドバーフィルタ ---
    st.sidebar.header("表示条件")
    sel_year = st.sidebar.selectbox("年度", years, index=0)
    sel_team = st.sidebar.selectbox("チーム", ["すべて"] + all_teams, index=0)

    # フィルタ用の年度（"すべて"ならNone）
    filter_year = sel_year if sel_year != "すべて" else None

    tab1, tab2 = st.tabs(["打撃成績", "投手成績"])

    # --- 3. 打撃成績タブ ---
    with tab1:
        st.subheader(f"⚾ 打撃部門 ({sel_year}年度 / {sel_team})")
        try:
            # 年度フィルタを適用して取得
            batting_list = db.get_batting_stats_filtered(sel_team, year=filter_year)
            if batting_list:
                df = pd.DataFrame(batting_list)
                mapping = {'name': '氏名', 'avg': '打率', 'ops': 'OPS', 'h': '安打', 'hr': '本塁打', 'rbi': '打点', 'sb': '盗塁', 'pa': '打席'}
                available_cols = [c for c in mapping.keys() if c in df.columns]
                disp_df = df[available_cols].rename(columns=mapping)
                
                num_cols = ["打率", "OPS", "安打", "本塁打", "打点", "盗塁", "打席"]
                disp_df[num_cols] = disp_df[num_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
                disp_df = disp_df.sort_values(by=["打率", "打席"], ascending=[False, False])
                
                st.dataframe(disp_df.style.format({"打率": "{:.3f}", "OPS": "{:.3f}"}).highlight_max(subset=["打率", "安打", "本塁打"], color="#e6f2ff"), use_container_width=True, hide_index=True)
            else:
                st.info("集計対象のデータがありません。")
        except Exception as e:
            st.error(f"打撃データ解析エラー: {e}")

    # --- 4. 投手成績タブ ---
    with tab2:
        st.subheader(f"🥎 投手部門 ({sel_year}年度 / {sel_team})")
        try:
            # 年度フィルタを適用して取得
            pitching_list = db.get_pitching_stats_filtered(sel_team, year=filter_year)
            
            if pitching_list:
                df_p = pd.DataFrame(pitching_list)
                df_p = df_p.dropna(subset=['name'])
                df_p = df_p[df_p['name'].str.strip() != ""]
                
                p_mapping = {'name': '氏名', 'total_win': '勝', 'total_loss': '敗', 'total_save': 'Ｓ', 'era': '防御率', 'total_ip': '投球回', 'total_so': '奪三振'}
                available_p_cols = [c for c in p_mapping.keys() if c in df_p.columns]
                disp_p_df = df_p[available_p_cols].rename(columns=p_mapping)
                
                num_p_cols = ["勝", "敗", "Ｓ", "防御率", "投球回", "奪三振"]
                disp_p_df[num_p_cols] = disp_p_df[num_p_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

                def format_ip(val):
                    base = int(val)
                    frac = round(val - base, 2)
                    if frac >= 0.3:
                        base += int(frac / 0.33)
                        rem = round((frac % 0.33) * 3, 0) / 10
                        return float(base + rem)
                    return float(val)
                
                disp_p_df["投球回"] = disp_p_df["投球回"].apply(format_ip)
                disp_p_df = disp_p_df.sort_values(by=["勝", "防御率", "投球回"], ascending=[False, True, False])
                
                st.dataframe(disp_p_df.style.format({"防御率": "{:.2f}", "投球回": "{:.1f}"}).highlight_max(subset=["勝", "奪三振"], color="#e6f2ff"), use_container_width=True, hide_index=True)
            else:
                st.info("集計対象のデータがありません。")
        except Exception as e:
            st.error(f"投手データ解析エラー: {e}")
