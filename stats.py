import streamlit as st
import pandas as pd
import database as db 

def show():
    st.title("🏆 チーム個人成績ランキング")

    # セッションから安全に取得
    role = st.session_state.get("user_role", "guest")
    username = st.session_state.get("username", "Guest")
    
    # --- 1. フィルタデータの準備 ---
    history = db.get_game_history()
    years = ["通算"]
    if history:
        # 重複を排除して降順ソート
        extracted_years = sorted(list(set([str(g.get('date', ''))[:4] for g in history if g.get('date')])), reverse=True)
        years.extend(extracted_years)

    all_teams = db.get_all_teams_in_order()
    
    # --- 2. サイドバーフィルタ ---
    st.sidebar.header("表示条件")
    default_year_idx = 1 if len(years) > 1 else 0
    sel_year = st.sidebar.selectbox("年度", years, index=default_year_idx)
    sel_team = st.sidebar.selectbox("チーム", ["すべて"] + all_teams, index=0)

    filter_year = sel_year if sel_year != "通算" else None

    tab1, tab2 = st.tabs(["⚾ 打撃成績", "🥎 投手成績"])

    # --- 3. 打撃成績タブ (詳細版) ---
    with tab1:
        st.subheader(f"⚾ 打撃部門 ({sel_year}年度 / {sel_team})")
        try:
            batting_list = db.get_batting_stats_filtered(sel_team, year=filter_year)
            if batting_list:
                df = pd.DataFrame(batting_list)
                
                # ユーザー指定の19項目に基づいたマッピング
                mapping = {
                    'name': '氏名', 'g': '試合', 'ab': '打数', 'pa': '打席', 'avg': '打率',
                    'h1': '単打', 'h2': '二塁', 'h3': '三塁', 'hr': '本塁',
                    'rbi': '打点', 'run': '得点', 'sb': '盗塁', 'bb': '四球',
                    'hbp': '死球', 'sh': '犠打', 'sf': '犠飛', 'so': '三振',
                    'obp': '出塁率', 'err': '失策'
                }
                
                # 存在するカラムのみを抽出し、表示順序を整理
                available_cols = [c for c in mapping.keys() if c in df.columns]
                disp_df = df[available_cols].rename(columns=mapping)
                
                # 数値型に変換
                num_cols = [c for c in disp_df.columns if c != '氏名']
                disp_df[num_cols] = disp_df[num_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
                
                # 打率 -> 打席数 の順で降順ソート
                disp_df = disp_df.sort_values(by=["打率", "打席"], ascending=[False, False])
                
                # フォーマット設定
                format_dict = {col: "{:d}" for col in num_cols}
                format_dict["打率"] = "{:.3f}"
                format_dict["出塁率"] = "{:.3f}"
                
                st.dataframe(
                    disp_df.style.format(format_dict)
                    .highlight_max(subset=["打率", "打点", "本塁", "盗塁"], color="#e6f2ff"),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption("※「単打〜本塁」は安打の内訳です。")
            else:
                st.info(f"{sel_year}年度の集計対象データがありません。")
        except Exception as e:
            st.error(f"打撃データ解析エラー: {e}")

    # --- 4. 投手成績タブ (項目拡充版) ---
    with tab2:
        st.subheader(f"🥎 投手部門 ({sel_year}年度 / {sel_team})")
        try:
            pitching_list = db.get_pitching_stats_filtered(sel_team, year=filter_year)
            
            if pitching_list:
                df_p = pd.DataFrame(pitching_list)
                df_p = df_p.dropna(subset=['name'])
                df_p = df_p[df_p['name'].str.strip() != ""]
                
                # ユーザー指定の16項目に基づいたマッピング
                p_mapping = {
                    'name': '氏名', 
                    'g': '登板', 
                    'total_ip': '投球回', 
                    'total_win': '勝', 
                    'total_loss': '敗', 
                    'total_save': 'Ｓ', 
                    'era': '防御率', 
                    'total_er': '自責点', 
                    'total_r': '失点', 
                    'total_so': '奪三振', 
                    'total_bb': '与四球', 
                    'total_hbp': '与死球', 
                    'total_h': '被安打', 
                    'total_hr': '被本塁打', 
                    'total_np': '投球数', 
                    'total_wp': '暴投'
                }
                
                available_p_cols = [c for c in p_mapping.keys() if c in df_p.columns]
                disp_p_df = df_p[available_p_cols].rename(columns=p_mapping)
                
                # 数値項目リスト（氏名以外すべて）
                num_p_cols = [c for c in disp_p_df.columns if c != '氏名']
                disp_p_df[num_p_cols] = disp_p_df[num_p_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

                # 投球回の表示形式変換関数
                def format_ip(val):
                    base = int(val)
                    frac = round(val - base, 2)
                    if frac >= 0.3:
                        # 0.33（1/3）単位での計算を想定
                        base += int(frac / 0.33)
                        rem = round((frac % 0.33) * 3, 0) / 10
                        return float(base + rem)
                    return float(val)
                
                disp_p_df["投球回"] = disp_p_df["投球回"].apply(format_ip)
                
                # 勝数 -> 防御率(昇順) -> 投球回の順でソート
                disp_p_df = disp_p_df.sort_values(by=["勝", "防御率", "投球回"], ascending=[False, True, False])
                
                # フォーマット設定
                p_format_dict = {col: "{:g}" for col in num_p_cols} # 基本は整数表示（不要な.0を消す）
                p_format_dict["防御率"] = "{:.2f}"
                p_format_dict["投球回"] = "{:.1f}"
                
                st.dataframe(
                    disp_p_df.style.format(p_format_dict)
                    .highlight_max(subset=["勝", "奪三振", "投球回"], color="#e6f2ff")
                    .highlight_min(subset=["防御率"], color="#fff2e6"),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.caption("※投球回は「イニング.アウト数」で表示しています。")
            else:
                st.info(f"{sel_year}年度の集計対象データがありません。")
        except Exception as e:
            st.error(f"投手データ解析エラー: {e}")