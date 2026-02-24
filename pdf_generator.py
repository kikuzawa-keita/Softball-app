import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors
import io
import os
from reportlab.lib.styles import getSampleStyleSheet

def generate_score_pdf(game_info, df_my, df_opp, df_pitching_my=None, df_pitching_opp=None):

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    font_path = "C:/Windows/Fonts/msgothic.ttc"
    font_name = 'Helvetica'
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('JP', font_path))
        font_name = 'JP'

    pitch_map = {
        "S": "○", "K": "◎", "B": "●", "F": "ー", "X": ""
    }

    def draw_scoreboard(y_pos):
        header = ["チーム", "1", "2", "3", "4", "5", "6", "7", "R"]

        gp = st.session_state.get("game_progress", {})
        is_finished = gp.get("is_finished", False)
        end_inn = gp.get("end_inning", 1)
        end_is_top = gp.get("end_is_top", True)
        is_bottom_x = gp.get("is_bottom_x", False)

        def safe_int_sum(scores):
            return sum([int(x) for x in scores if str(x).isdigit()])


    # ■スコアボード-------------

    def draw_scoreboard(y_pos):
        header = ["チーム", "HC", "1", "2", "3", "4", "5", "6", "7", "R"]

        gp = st.session_state.get("game_progress", {})

        setup = st.session_state.get("game_setup", {})
        my_hc = int(setup.get("my_handicap", 0) or 0)
        opp_hc = int(setup.get("opp_handicap", 0) or 0)

        is_finished = gp.get("is_finished", False)
        end_inn = gp.get("end_inning", 1)
        end_is_top = gp.get("end_is_top", True)
        is_bottom_x = gp.get("is_bottom_x", False)

        def safe_int_sum(scores):
            return sum([int(x) for x in scores if str(x).isdigit()])

        def get_formatted_scores(scores_raw, is_top_row):
            res = []
            for i in range(7):
                target_inn = i + 1
                val = scores_raw[i] if i < len(scores_raw) else ""
                
                if is_finished:
                    if target_inn < end_inn:
                        res.append(str(val) if val != "" else "0")
                    elif target_inn == end_inn:
                        if is_top_row:
                            res.append(str(val) if val != "" else "0")
                        else: 
                            if is_bottom_x:
                                res.append("×")
                            elif val != "":  
                                res.append(str(val))
                            elif not end_is_top:
                                res.append("0")
                            else:
                                res.append("")
                    else:
                        res.append("")
                else:

                    curr_inn = gp.get("inning", 1)
                    if target_inn < curr_inn:
                        res.append(str(val) if val != "" else "0")
                    elif target_inn == curr_inn:
                        if is_top_row:
                            res.append(str(val) if val != "" else "0")
                        else:
                            if val != "":
                                res.append(str(val))
                            elif not gp.get("is_top"):
                                res.append("0")
                            else:
                                res.append("")
                    else:
                        res.append("")
            return res

        top_scores = get_formatted_scores(game_info.get('top_scores', []), True)
        bot_scores = get_formatted_scores(game_info.get('bottom_scores', []), False)

        total_top = safe_int_sum(game_info.get('top_scores', [])) + opp_hc
        total_bot = safe_int_sum(game_info.get('bottom_scores', [])) + my_hc

        top_row = [
            game_info['opp_team'][:10], 
            str(opp_hc) if opp_hc > 0 else "", 
            *top_scores, 
            total_top
        ]
        bot_row = [
            game_info['my_team'][:10], 
            str(my_hc) if my_hc > 0 else "", 
            *bot_scores, 
            total_bot
        ]
        
        data = [header, top_row, bot_row]

        col_widths = [80, 30] + [35]*7 + [40]
        
        sb_table = Table(data, colWidths=col_widths, rowHeights=20)
        sb_table.setStyle(TableStyle([
            ('FONT', (0,0), (-1,-1), font_name, 10),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        sb_table.wrapOn(c, width, height)
        sb_table.drawOn(c, 50, y_pos)
        return y_pos - 60


    # ■打者成績-------------

    def draw_player_table(df, y_pos):    
        if df is None or df.empty:
            return y_pos

        styles = getSampleStyleSheet()
        cell_style = styles["BodyText"].clone('cell_style') 
        cell_style.fontName = font_name
        cell_style.fontSize = 7
        cell_style.leading = 8     
        cell_style.alignment = 1   

        data = []

        data.append(df.columns.tolist())

        for _, row in df.iterrows():
            new_row = []
            for item in row:
                s_item = str(item)

                display_text = s_item.replace("\n", "<br/>")

                if "一単打" in display_text:
                    display_text = display_text.replace("一単打", '<font color="red">一単打</font>')
                if "二単打" in display_text:
                    display_text = display_text.replace("二単打", '<font color="red">二単打</font>')
                if "三単打" in display_text:
                    display_text = display_text.replace("三単打", '<font color="red">三単打</font>')
                if "遊単打" in display_text:
                    display_text = display_text.replace("遊単打", '<font color="red">遊単打</font>')
                if "左単打" in display_text:
                    display_text = display_text.replace("左単打", '<font color="red">左単打</font>')
                if "中単打" in display_text:
                    display_text = display_text.replace("中単打", '<font color="red">中単打</font>')
                if "右単打" in display_text:
                    display_text = display_text.replace("右単打", '<font color="red">右単打</font>')
                if "投単打" in display_text:
                    display_text = display_text.replace("投単打", '<font color="red">投単打</font>')
                if "捕単打" in display_text:
                    display_text = display_text.replace("捕単打", '<font color="red">捕単打</font>')
                if "左二塁打" in display_text:
                    display_text = display_text.replace("左二塁打", '<font color="red">左二塁打</font>')
                if "中二塁打" in display_text:
                    display_text = display_text.replace("中二塁打", '<font color="red">中二塁打</font>')
                if "右二塁打" in display_text:
                    display_text = display_text.replace("右二塁打", '<font color="red">右二塁打</font>')
                if "左三塁打" in display_text:
                    display_text = display_text.replace("左三塁打", '<font color="red">左三塁打</font>')
                if "中三塁打" in display_text:
                    display_text = display_text.replace("中三塁打", '<font color="red">中三塁打</font>')
                if "右三塁打" in display_text:
                    display_text = display_text.replace("右三塁打", '<font color="red">右三塁打</font>')
                if "左本塁打" in display_text:
                    display_text = display_text.replace("左本塁打", '<font color="red">左本塁打</font>')
                if "中本塁打" in display_text:
                    display_text = display_text.replace("中本塁打", '<font color="red">中本塁打</font>')
                if "右本塁打" in display_text:
                    display_text = display_text.replace("右本塁打", '<font color="red">右本塁打</font>')
                if "四球" in display_text:
                    display_text = display_text.replace("四球", '<font color="orange">四球</font>')
                if "死球" in display_text:
                    display_text = display_text.replace("死球", '<font color="orange">死球</font>')
                if "投野選" in display_text:
                    display_text = display_text.replace("投野選", '<font color="orange">投野選</font>')
                if "捕野選" in display_text:
                    display_text = display_text.replace("捕野選", '<font color="orange">捕野選</font>')
                if "一野選" in display_text:
                    display_text = display_text.replace("一野選", '<font color="orange">一野選</font>')
                if "二野選" in display_text:
                    display_text = display_text.replace("二野選", '<font color="orange">二野選</font>')
                if "三野選" in display_text:
                    display_text = display_text.replace("三野選", '<font color="orange">三野選</font>')
                if "遊野選" in display_text:
                    display_text = display_text.replace("遊野選", '<font color="orange">遊野選</font>')
                if "投失" in display_text:
                    display_text = display_text.replace("投失", '<font color="orange">投失</font>')
                if "捕失" in display_text:
                    display_text = display_text.replace("捕失", '<font color="orange">捕失</font>')
                if "一失" in display_text:
                    display_text = display_text.replace("一失", '<font color="orange">一失</font>')
                if "二失" in display_text:
                    display_text = display_text.replace("二失", '<font color="orange">二失</font>')
                if "三失" in display_text:
                    display_text = display_text.replace("三失", '<font color="orange">三失</font>')
                if "遊失" in display_text:
                    display_text = display_text.replace("遊失", '<font color="orange">遊失</font>')
                if "左失" in display_text:
                    display_text = display_text.replace("左失", '<font color="orange">左失</font>')
                if "中失" in display_text:
                    display_text = display_text.replace("中失", '<font color="orange">中失</font>')
                if "右失" in display_text:
                    display_text = display_text.replace("右失", '<font color="orange">右失</font>')

                p_item = Paragraph(
                    f'<font name="{font_name}" size="7">{display_text}</font>', 
                    cell_style
                )
                new_row.append(p_item)
            data.append(new_row)

        col_widths = [20, 25, 70] + [42]*7 + [22, 22, 22, 22]
        row_heights = [20] + [35] * (len(data) - 1)
        
        t = Table(data, colWidths=col_widths, rowHeights=row_heights)
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,-1), font_name, 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('LEFTPADDING', (0,0), (-1,-1), 1),
            ('RIGHTPADDING', (0,0), (-1,-1), 1),
        ]))
        
        t.wrapOn(c, width, height)
        table_height = sum(row_heights)
        t.drawOn(c, 30, y_pos - table_height)
        return y_pos - table_height - 30


    # ■投手成績-------------

    def draw_pitching_table(df, y_pos, title):
        if df is None or df.empty:
            return y_pos
        
        c.setFont(font_name, 10)
        c.drawString(50, y_pos, f"■ {title}")
        y_pos -= 15

        header = ["投手名", "回", "球", "安", "本", "振", "WP", "四", "死", "点", "責", "勝敗"]

        rows = []
        for _, r in df.iterrows():
            row = [
                r.get("名前", r.get("投手名", "")),
                r.get("イニング", ""),
                r.get("球数", ""),
                r.get("被安打", ""),
                r.get("被本塁打", ""),
                r.get("奪三振", ""),
                r.get("WP", ""),
                r.get("与四球", ""),
                r.get("与死球", ""),
                r.get("失点", ""),
                r.get("自責点", ""),
                r.get("勝敗", "")
            ]
            rows.append(row)
        
        data = [header] + rows

        col_widths = [75, 30, 30, 25, 25, 25, 25, 25, 25, 25, 25, 40]
        
        t = Table(data, colWidths=col_widths, rowHeights=20)
        t.setStyle(TableStyle([
            ('FONT', (0,0), (-1,-1), font_name, 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        t.wrapOn(c, width, height)
        table_height = len(data) * 20
        t.drawOn(c, 50, y_pos - table_height)
        return y_pos - table_height - 30


    # ■footer-------------

    def draw_footer():
        c.setFont(font_name, 8)
        footer_text = "配球記号　○：見逃し　◎：空振り　●：ボール　ー：ファール"
        c.drawString(50, 30, footer_text)

    c.setFont(font_name, 14)
    c.drawString(50, height - 40, f"試合記録: {game_info['date']}")
    curr_y = draw_scoreboard(height - 105)
    
    c.setFont(font_name, 11)
    c.drawString(50, curr_y, f"▼ {game_info['my_team']} 攻撃成績")
    curr_y = draw_player_table(df_my, curr_y - 10)

    if df_pitching_my is not None:
        curr_y = draw_pitching_table(df_pitching_my, curr_y, f"{game_info['my_team']} 投手成績")
    
    draw_footer()
    c.showPage()

    c.setFont(font_name, 14)
    c.drawString(50, height - 40, f"試合記録: {game_info['date']}")
    curr_y = draw_scoreboard(height - 105)
    
    c.setFont(font_name, 11)
    c.drawString(50, curr_y, f"▼ {game_info['opp_team']} 攻撃成績")
    curr_y = draw_player_table(df_opp, curr_y - 10)

    if df_pitching_opp is not None:
        curr_y = draw_pitching_table(df_pitching_opp, curr_y, f"{game_info['opp_team']} 投手成績")
        
    draw_footer()
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer