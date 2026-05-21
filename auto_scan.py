"""
auto_scan.py
GitHub Actionsから呼ばれる自動スキャン＋メール送信＋スプレッドシート記録
9時〜15時・1時間おきに実行
買いシグナル: デイトレ（日足順張り）・マルチTF・押し目
売りシグナル: 信用売り（日足・1h・5分）
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json, os, smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# gspread は任意（GOOGLE_CREDENTIALS未設定なら無視）
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ── 設定 ──────────────────────────────────────────────────────
ALERT_TO          = "kamejirou1@gmail.com"
GMAIL_USER        = os.environ.get("GMAIL_USER", "")
GMAIL_PASS        = os.environ.get("GMAIL_PASS", "")
SPREADSHEET_ID    = os.environ.get("SPREADSHEET_ID", "")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
TICKER_FILE = os.path.join(BASE_DIR, "kabu3_tickers.json")

# ── 銘柄読み込み ───────────────────────────────────────────────
with open(TICKER_FILE, "r", encoding="utf-8") as f:
    all_tickers_dict = json.load(f)

TARGET = {name: code
          for sec in all_tickers_dict.values()
          for name, code in sec.items()
          if not code.endswith("=X")}  # 為替除く

# ── 指標計算 ───────────────────────────────────────────────────
def calc_indicators(df):
    c = df["Close"]
    for w in [5, 25, 75]:
        df[f"MA_{w}"] = c.rolling(w).mean()
    df["BB_Mid"]   = c.rolling(20).mean()
    df["BB_Std"]   = c.rolling(20).std()
    df["BB_Upper"] = df["BB_Mid"] + df["BB_Std"] * 2
    df["BB_Lower"] = df["BB_Mid"] - df["BB_Std"] * 2
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]
    delta = c.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14).mean()
    loss  = -delta.clip(upper=0).ewm(alpha=1/14, min_periods=14).mean()
    df["RSI"] = 100 - (100 / (1 + gain / loss))
    low14  = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()
    df["Stoch_K"] = 100 * (c - low14) / (high14 - low14)
    df["Stoch_D"] = df["Stoch_K"].rolling(3).mean()
    return df

# ── 日足トレンド確認 ───────────────────────────────────────────
def get_daily_trend(code):
    """
    戻り値: "up"（上昇） / "down"（下降） / "none"（判定不能）
    上昇: MA5 > MA25 > MA75
    下降: MA5 < MA25 < MA75
    """
    try:
        df = yf.download(code, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 80:
            return "none"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how="all", inplace=True)
        for w in [5, 25, 75]:
            df[f"MA_{w}"] = df["Close"].rolling(w).mean()
        last = df.iloc[-1]
        ma5  = float(last["MA_5"])
        ma25 = float(last["MA_25"])
        ma75 = float(last["MA_75"])
        if ma5 > ma25 > ma75:
            return "up"
        if ma5 < ma25 < ma75:
            return "down"
        return "none"
    except Exception:
        return "none"

# ── マルチTFスキャン（買い）────────────────────────────────────
def scan_multi_tf(code, name):
    results = {}
    configs = {
        "日足":    ("1d", "1y"),
        "1時間足": ("1h", "3mo"),
        "5分足":   ("5m", "5d"),
    }
    for tf_label, (interval, period) in configs.items():
        try:
            df = yf.download(code, period=period, interval=interval, progress=False)
            if df.empty or len(df) < 50:
                results[tf_label] = "❓"; continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.dropna(how="all", inplace=True)
            df = calc_indicators(df)
            last = df.iloc[-1]; prev = df.iloc[-2]

            price  = float(last["Close"])
            ma25   = float(last["MA_25"])
            ma75   = float(last["MA_75"])
            rsi    = float(last["RSI"])
            macd_h = float(last["MACD_Hist"])
            macd_hp= float(prev["MACD_Hist"])
            stoch  = float(last["Stoch_K"])
            bb_upper = float(last["BB_Upper"])

            uptrend  = price > ma75
            near_ma25= abs(price - ma25) / ma25 < 0.08
            macd_gc  = float(prev["MACD"]) <= float(prev["MACD_Signal"]) and float(last["MACD"]) > float(last["MACD_Signal"])
            macd_up  = macd_h > macd_hp
            stoch_gc = float(prev["Stoch_K"]) <= float(prev["Stoch_D"]) and stoch > float(last["Stoch_D"])
            not_ob   = stoch < 70 and rsi < 65

            buy  = uptrend and near_ma25 and (macd_gc or (stoch_gc and stoch < 40)) and macd_up and not_ob
            sell = rsi > 70 or price >= bb_upper * 0.99

            results[tf_label]             = "🟢" if buy else "🔴" if sell else "➖"
            results[f"RSI({tf_label})"]   = round(rsi, 1)
            results[f"Stoch({tf_label})"] = round(stoch, 1)
        except Exception:
            results[tf_label] = "❓"
    return results

# ── 押し目買いスキャン（日足）──────────────────────────────────
def scan_oshime(code, name):
    try:
        df = yf.download(code, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 80:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how="all", inplace=True)
        df = calc_indicators(df)

        last  = df.iloc[-1]; prev = df.iloc[-2]; prev2 = df.iloc[-3]
        price = float(last["Close"])
        ma5   = float(last["MA_5"]); ma25 = float(last["MA_25"]); ma75 = float(last["MA_75"])
        rsi   = float(last["RSI"]); rsi_prev = float(prev["RSI"])
        bb_lower  = float(last["BB_Lower"])
        macd_h    = float(last["MACD_Hist"]); macd_hp = float(prev["MACD_Hist"])

        if not (ma5 > ma25 > ma75):
            return None
        if float(df["RSI"].iloc[-5:].min()) > 32:
            return None
        if not (rsi > rsi_prev or rsi > float(prev2["RSI"])):
            return None
        if not any(float(df["Low"].iloc[i]) <= float(df["BB_Lower"].iloc[i]) * 1.01 for i in range(-5, 0)):
            return None
        if price >= float(df["High"].max()) * 0.95:
            return None

        near_ma25   = abs(price - ma25) / ma25 * 100 <= 5.0
        macd_bottom = macd_h > macd_hp
        reasons = ["RSI売られすぎ", "BB下限タッチ"]
        score = 7
        if macd_bottom: score += 2; reasons.append("MACD底打ち")
        if near_ma25:   score += 2; reasons.append("MA25付近")

        return {
            "銘柄名": name, "コード": code,
            "株価": round(price, 1), "RSI": round(rsi, 1),
            "エントリー": round(price, 1),
            "損切り": round(bb_lower * 0.98, 1),
            "利確目標": round(ma25 * 1.10, 1),
            "根拠": " / ".join(reasons), "スコア": score,
        }
    except Exception:
        return None

# ── デイトレ買いスキャン（1h）──────────────────────────────────
def scan_daytrade_buy_1h(code, name):
    """日足上昇トレンド中の1h押し目買い"""
    if get_daily_trend(code) != "up":
        return None
    try:
        df = yf.download(code, period="30d", interval="1h", progress=False)
        if df.empty or len(df) < 50:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how="all", inplace=True)
        df = calc_indicators(df)

        last = df.iloc[-1]; prev = df.iloc[-2]
        price = float(last["Close"]); ma25 = float(last["MA_25"])
        rsi = float(last["RSI"]); rsi_prev = float(prev["RSI"])
        bb_lower = float(last["BB_Lower"])
        macd_h = float(last["MACD_Hist"]); macd_hp = float(prev["MACD_Hist"])

        rsi_min = float(df["RSI"].iloc[-8:].min())
        if rsi_min > 35 or not (rsi > rsi_prev):
            return None
        if not any(float(df["Low"].iloc[i]) <= float(df["BB_Lower"].iloc[i]) * 1.01 for i in range(-8, 0)):
            return None

        macd_bottom = macd_h > macd_hp
        near_ma25   = abs(price - ma25) / ma25 * 100 <= 5.0

        score = 4; reasons = ["日足↑", "RSI売られすぎ(1h)", "BB下限(1h)"]
        if macd_bottom: score += 2; reasons.append("MACD底打ち(1h)")
        if near_ma25:   score += 2; reasons.append("MA25付近(1h)")

        return {
            "銘柄名": name, "コード": code, "種別": "DT買い1h",
            "株価": round(price, 1), "RSI": round(rsi, 1),
            "RSI最小": round(rsi_min, 1), "BB下限": round(bb_lower, 1),
            "スコア": score,
            "エントリー": round(price, 1),
            "損切り": round(bb_lower * 0.98, 1),
            "利確目標": round(price * 1.03, 1),
            "根拠": " / ".join(reasons),
        }
    except Exception:
        return None

# ── デイトレ買いスキャン（5m）──────────────────────────────────
def scan_daytrade_buy_5m(code, name):
    """日足上昇トレンド中の5分押し目買い"""
    if get_daily_trend(code) != "up":
        return None
    try:
        df = yf.download(code, period="5d", interval="5m", progress=False)
        if df.empty or len(df) < 50:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how="all", inplace=True)
        df = calc_indicators(df)

        last = df.iloc[-1]; prev = df.iloc[-2]
        price = float(last["Close"]); ma25 = float(last["MA_25"])
        rsi = float(last["RSI"]); rsi_prev = float(prev["RSI"])
        bb_lower = float(last["BB_Lower"])
        macd_h = float(last["MACD_Hist"]); macd_hp = float(prev["MACD_Hist"])

        rsi_min = float(df["RSI"].iloc[-12:].min())
        if rsi_min > 32 or not (rsi > rsi_prev):
            return None
        if not any(float(df["Low"].iloc[i]) <= float(df["BB_Lower"].iloc[i]) * 1.01 for i in range(-12, 0)):
            return None

        macd_bottom = macd_h > macd_hp
        near_ma25   = abs(price - ma25) / ma25 * 100 <= 3.0

        score = 4; reasons = ["日足↑", "RSI売られすぎ(5m)", "BB下限(5m)"]
        if macd_bottom: score += 2; reasons.append("MACD底打ち(5m)")
        if near_ma25:   score += 2; reasons.append("MA25付近(5m)")

        return {
            "銘柄名": name, "コード": code, "種別": "DT買い5m",
            "株価": round(price, 1), "RSI": round(rsi, 1),
            "RSI最小": round(rsi_min, 1), "BB下限": round(bb_lower, 1),
            "スコア": score,
            "エントリー": round(price, 1),
            "損切り": round(bb_lower * 0.99, 1),
            "利確目標": round(price * 1.015, 1),
            "根拠": " / ".join(reasons),
        }
    except Exception:
        return None

# ── 信用売りスキャン（日足）────────────────────────────────────
def scan_short_daily(code, name):
    """日足下降トレンド中の戻り売り"""
    try:
        df = yf.download(code, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 80:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how="all", inplace=True)
        df = calc_indicators(df)

        last  = df.iloc[-1]; prev = df.iloc[-2]; prev2 = df.iloc[-3]
        price = float(last["Close"])
        ma5   = float(last["MA_5"]); ma25 = float(last["MA_25"]); ma75 = float(last["MA_75"])
        rsi   = float(last["RSI"]); rsi_prev = float(prev["RSI"])
        bb_upper  = float(last["BB_Upper"])
        macd_h    = float(last["MACD_Hist"]); macd_hp = float(prev["MACD_Hist"])

        if not (ma5 < ma25 < ma75):
            return None
        rsi_max5 = float(df["RSI"].iloc[-5:].max())
        if rsi_max5 < 60:
            return None
        if not (rsi < rsi_prev or rsi < float(prev2["RSI"])):
            return None
        if not any(float(df["High"].iloc[i]) >= float(df["BB_Upper"].iloc[i]) * 0.99 for i in range(-5, 0)):
            return None
        if price <= float(df["Low"].min()) * 1.05:
            return None

        near_ma25  = abs(price - ma25) / ma25 * 100 <= 5.0
        macd_top   = macd_h < macd_hp
        reasons = ["RSI高値圏", "BB上限タッチ", "RSI反落"]
        score = 9
        if macd_top:  score += 2; reasons.append("MACD天井打ち")
        if near_ma25: score += 2; reasons.append("MA25付近")

        return {
            "銘柄名": name, "コード": code, "種別": "日足売り",
            "株価": round(price, 1), "RSI": round(rsi, 1),
            "エントリー(売)": round(price, 1),
            "損切り(買戻)": round(bb_upper * 1.02, 1),
            "利確目標": round(ma25 * 0.92, 1),
            "根拠": " / ".join(reasons), "スコア": score,
        }
    except Exception:
        return None

# ── 信用売りスキャン（1h）──────────────────────────────────────
def scan_short_1h(code, name):
    """日足下降トレンド中の1h戻り売り"""
    if get_daily_trend(code) != "down":
        return None
    try:
        df = yf.download(code, period="30d", interval="1h", progress=False)
        if df.empty or len(df) < 50:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how="all", inplace=True)
        df = calc_indicators(df)

        last = df.iloc[-1]; prev = df.iloc[-2]
        price = float(last["Close"]); ma25 = float(last["MA_25"])
        rsi = float(last["RSI"]); rsi_prev = float(prev["RSI"])
        bb_upper = float(last["BB_Upper"])
        macd_h = float(last["MACD_Hist"]); macd_hp = float(prev["MACD_Hist"])

        rsi_max = float(df["RSI"].iloc[-8:].max())
        if rsi_max < 60 or not (rsi < rsi_prev):
            return None
        if not any(float(df["High"].iloc[i]) >= float(df["BB_Upper"].iloc[i]) * 0.99 for i in range(-8, 0)):
            return None

        macd_top  = macd_h < macd_hp
        near_ma25 = abs(price - ma25) / ma25 * 100 <= 5.0

        score = 4; reasons = ["日足↓", "RSI高値(1h)", "BB上限(1h)"]
        if macd_top:  score += 2; reasons.append("MACD天井(1h)")
        if near_ma25: score += 2; reasons.append("MA25付近(1h)")

        return {
            "銘柄名": name, "コード": code, "種別": "DT売り1h",
            "株価": round(price, 1), "RSI": round(rsi, 1),
            "スコア": score,
            "エントリー(売)": round(price, 1),
            "損切り(買戻)": round(bb_upper * 1.02, 1),
            "利確目標": round(price * 0.97, 1),
            "根拠": " / ".join(reasons),
        }
    except Exception:
        return None

# ── 信用売りスキャン（5m）──────────────────────────────────────
def scan_short_5m(code, name):
    """日足下降トレンド中の5分戻り売り"""
    if get_daily_trend(code) != "down":
        return None
    try:
        df = yf.download(code, period="5d", interval="5m", progress=False)
        if df.empty or len(df) < 50:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how="all", inplace=True)
        df = calc_indicators(df)

        last = df.iloc[-1]; prev = df.iloc[-2]
        price = float(last["Close"]); ma25 = float(last["MA_25"])
        rsi = float(last["RSI"]); rsi_prev = float(prev["RSI"])
        bb_upper = float(last["BB_Upper"])
        macd_h = float(last["MACD_Hist"]); macd_hp = float(prev["MACD_Hist"])

        rsi_max = float(df["RSI"].iloc[-12:].max())
        if rsi_max < 62 or not (rsi < rsi_prev):
            return None
        if not any(float(df["High"].iloc[i]) >= float(df["BB_Upper"].iloc[i]) * 0.99 for i in range(-12, 0)):
            return None

        macd_top  = macd_h < macd_hp
        near_ma25 = abs(price - ma25) / ma25 * 100 <= 3.0

        score = 4; reasons = ["日足↓", "RSI高値(5m)", "BB上限(5m)"]
        if macd_top:  score += 2; reasons.append("MACD天井(5m)")
        if near_ma25: score += 2; reasons.append("MA25付近(5m)")

        return {
            "銘柄名": name, "コード": code, "種別": "DT売り5m",
            "株価": round(price, 1), "RSI": round(rsi, 1),
            "スコア": score,
            "エントリー(売)": round(price, 1),
            "損切り(買戻)": round(bb_upper * 1.01, 1),
            "利確目標": round(price * 0.985, 1),
            "根拠": " / ".join(reasons),
        }
    except Exception:
        return None

# ── スプレッドシート書き込み ────────────────────────────────────
def write_to_spreadsheet(rows, sheet_name="デイトレ"):
    if not HAS_GSPREAD or not SPREADSHEET_ID or not GOOGLE_CREDS_JSON:
        print("スプレッドシート設定なし")
        return
    try:
        import json as _json
        creds_dict = _json.loads(GOOGLE_CREDS_JSON)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        wb     = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = wb.worksheet(sheet_name)
        except Exception:
            sheet = wb.add_worksheet(title=sheet_name, rows=1000, cols=20)

        existing = sheet.get_all_values()
        if not existing:
            sheet.append_row(["日時","銘柄名","コード","種別","株価","エントリー","損切り","利確目標","RSI","スコア","根拠"])

        for r in rows:
            entry  = r.get("エントリー", r.get("エントリー(売)", ""))
            stop   = r.get("損切り",     r.get("損切り(買戻)", ""))
            sheet.append_row([
                r.get("日時",""), r.get("銘柄名",""), r.get("コード",""),
                r.get("種別",""), r.get("株価",""),
                entry, stop, r.get("利確目標",""),
                r.get("RSI",""), r.get("スコア",""), r.get("根拠",""),
            ])
        print(f"✅ スプレッドシート[{sheet_name}]書き込み完了: {len(rows)}件")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {e}")

# ── HTMLメール送信 ─────────────────────────────────────────────
def send_mail(subject, buy_signals, oshime_list, daytrade_buy, short_signals):
    if not GMAIL_USER or not GMAIL_PASS:
        print("メール設定なし（GMAIL_USER / GMAIL_PASS 未設定）")
        return
    time_str = datetime.now().strftime("%m/%d %H:%M")
    total    = len(buy_signals) + len(oshime_list) + len(daytrade_buy) + len(short_signals)

    def card(color, emoji, title, body_html):
        return f"""
        <div style="margin:14px 0;border-radius:10px;overflow:hidden;border:1px solid {color};">
          <div style="background:{color};color:#fff;padding:10px 16px;font-size:15px;font-weight:bold;">
            {emoji} {title}
          </div>
          <div style="background:#1a1a2e;padding:10px 14px;">{body_html}</div>
        </div>"""

    def row_buy(r, kind="buy"):
        name   = r.get("銘柄名",""); code = r.get("コード","")
        entry  = r.get("エントリー", r.get("エントリー(売)", 0))
        stop   = r.get("損切り",     r.get("損切り(買戻)", 0))
        target = r.get("利確目標", 0)
        rsi    = r.get("RSI","")
        reason = r.get("根拠","")
        if kind == "sell":
            profit_pct = round((entry - target) / entry * 100, 1) if entry else 0
            loss_pct   = round((stop - entry)   / entry * 100, 1) if entry else 0
            e_label = "売りエントリー"; e_color = "#ef4444"
            t_label = "利確(買戻)";     t_color = "#00d4aa"
            s_label = "損切り(買戻)";   s_color = "#fbbf24"
            t_str = f"¥{target:,} <span style='font-size:11px'>-{profit_pct}%</span>"
            s_str = f"¥{stop:,} <span style='font-size:11px'>+{loss_pct}%</span>"
        else:
            profit_pct = round((target - entry) / entry * 100, 1) if entry else 0
            loss_pct   = round((entry - stop)   / entry * 100, 1) if entry else 0
            e_label = "エントリー";  e_color = "#00d4aa"
            t_label = "利確目標";    t_color = "#00d4aa"
            s_label = "損切り";      s_color = "#ef4444"
            t_str = f"¥{target:,} <span style='font-size:11px'>+{profit_pct}%</span>"
            s_str = f"¥{stop:,} <span style='font-size:11px'>-{loss_pct}%</span>"
        return f"""
        <div style="border-bottom:1px solid #2a2a4a;padding:10px 0;">
          <b style="color:#e2e8f0;font-size:14px;">{name}
            <span style="color:#94a3b8;font-size:12px;">（{code}）</span>
          </b>
          <div style="display:flex;gap:10px;margin-top:8px;flex-wrap:wrap;">
            <div style="background:#0f2040;border-radius:6px;padding:6px 10px;min-width:90px;">
              <div style="font-size:10px;color:#64748b;">{e_label}</div>
              <div style="font-size:14px;color:{e_color};font-weight:bold;">¥{entry:,}</div>
            </div>
            <div style="background:#0f2040;border-radius:6px;padding:6px 10px;min-width:90px;">
              <div style="font-size:10px;color:#64748b;">{t_label}</div>
              <div style="font-size:14px;color:{t_color};font-weight:bold;">{t_str}</div>
            </div>
            <div style="background:#0f2040;border-radius:6px;padding:6px 10px;min-width:90px;">
              <div style="font-size:10px;color:#64748b;">{s_label}</div>
              <div style="font-size:14px;color:{s_color};font-weight:bold;">{s_str}</div>
            </div>
          </div>
          <div style="font-size:11px;color:#94a3b8;margin-top:6px;">
            RSI: {rsi} &nbsp;｜&nbsp; 根拠: {reason}
          </div>
        </div>"""

    sections = ""

    if daytrade_buy:
        rows_html = "".join(row_buy(r, "buy") for r in daytrade_buy)
        sections += card("#0891b2", "⚡", f"デイトレ買い（日足↑順張り）　{len(daytrade_buy)}銘柄", rows_html)

    if short_signals:
        rows_html = "".join(row_buy(r, "sell") for r in short_signals)
        sections += card("#dc2626", "🔻", f"信用売りシグナル（日足↓戻り売り）　{len(short_signals)}銘柄", rows_html)

    if buy_signals:
        rows_html = "".join(row_buy(r, "buy") for r in sorted(buy_signals, key=lambda x: -x.get("一致数",0)))
        sections += card("#ea580c", "🔥", f"マルチTF買い（2TF以上一致）　{len(buy_signals)}銘柄", rows_html)

    if oshime_list:
        rows_html = "".join(row_buy(r, "buy") for r in sorted(oshime_list, key=lambda x: -x.get("スコア",0)))
        sections += card("#7c3aed", "📉", f"押し目買い（日足）　{len(oshime_list)}銘柄", rows_html)

    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0d1117;color:#e2e8f0;
             font-family:'Helvetica Neue',Arial,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:14px;">
    <div style="background:linear-gradient(135deg,#1e3a5f,#0f2a3f);
                border-radius:12px;padding:18px;margin-bottom:14px;
                border:1px solid #00d4aa;">
      <div style="font-size:20px;font-weight:bold;color:#00d4aa;">📈 kabu3 スキャン結果</div>
      <div style="font-size:13px;color:#94a3b8;margin-top:4px;">
        {time_str} &nbsp;｜&nbsp; 合計 {total} 件
      </div>
    </div>
    {sections}
    <div style="margin-top:14px;padding:10px;background:#111827;border-radius:8px;
                font-size:11px;color:#64748b;text-align:center;">
      ⚠️ 投資判断はご自身の責任でお願いします。このメールは自動送信です。
    </div>
  </div>
</body></html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = GMAIL_USER
        msg["To"]      = ALERT_TO
        msg["Subject"] = f"📈 kabu3 {time_str}（{total}件）"
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, ALERT_TO, msg.as_string())
        print(f"✅ メール送信完了: {subject}（{total}件）")
    except Exception as e:
        print(f"❌ メール送信失敗: {e}")

# ── メイン ─────────────────────────────────────────────────────
def main():
    now      = datetime.now()
    time_str = now.strftime("%m/%d %H:%M")
    print(f"[{time_str}] 自動スキャン開始 対象:{len(TARGET)}銘柄")

    buy_signals  = []   # マルチTF（2TF以上）
    oshime_list  = []   # 押し目（日足）
    daytrade_buy = []   # デイトレ買い（1h＋5分 両方シグナル）
    short_list   = []   # 信用売り（1h＋5分 両方シグナル or 日足売り）

    for i, (name, code) in enumerate(TARGET.items()):
        print(f"  {i+1}/{len(TARGET)} {name}", end="\r")
        try:
            # ① マルチTFスキャン（買い）
            tf_result = scan_multi_tf(code, name)
            buy_count = sum(1 for k in ["日足","1時間足","5分足"] if tf_result.get(k) == "🟢")
            if buy_count >= 2:
                buy_signals.append({
                    "銘柄名": name, "コード": code,
                    "日足": tf_result.get("日足","❓"),
                    "1時間足": tf_result.get("1時間足","❓"),
                    "5分足": tf_result.get("5分足","❓"),
                    "一致数": buy_count,
                    "RSI": tf_result.get("RSI(日足)","−"),
                    "エントリー": 0, "損切り": 0, "利確目標": 0,
                    "根拠": f"{buy_count}TF一致",
                })

            # ② 押し目スキャン（日足）
            ro = scan_oshime(code, name)
            if ro: oshime_list.append(ro)

            # ③ デイトレ買い（1h＋5分 両方）
            rb1h = scan_daytrade_buy_1h(code, name)
            rb5m = scan_daytrade_buy_5m(code, name)
            if rb1h and rb5m:
                daytrade_buy.append({
                    "銘柄名": name, "コード": code, "種別": "DT買い両TF",
                    "株価": rb1h["株価"], "RSI": rb1h["RSI"],
                    "エントリー": rb1h["エントリー"],
                    "損切り": rb1h["損切り"],
                    "利確目標": rb1h["利確目標"],
                    "根拠": rb1h["根拠"],
                    "スコア": rb1h["スコア"],
                    "日時": time_str,
                })

            # ④ 信用売り
            rs_d  = scan_short_daily(code, name)
            rs_1h = scan_short_1h(code, name)
            rs_5m = scan_short_5m(code, name)
            if rs_1h and rs_5m:   # デイトレ売り（両TF）
                short_list.append({
                    "銘柄名": name, "コード": code, "種別": "DT売り両TF",
                    "株価": rs_1h["株価"], "RSI": rs_1h["RSI"],
                    "エントリー(売)": rs_1h["エントリー(売)"],
                    "損切り(買戻)":   rs_1h["損切り(買戻)"],
                    "利確目標":       rs_1h["利確目標"],
                    "根拠": rs_1h["根拠"],
                    "スコア": rs_1h["スコア"],
                    "日時": time_str,
                })
            elif rs_d and rs_d.get("スコア",0) >= 9:   # 日足売り（高スコアのみ）
                rs_d["日時"] = time_str
                short_list.append(rs_d)

        except Exception:
            pass

    print(f"\nマルチTF買い:{len(buy_signals)} 押し目:{len(oshime_list)} "
          f"DT買い:{len(daytrade_buy)} 信用売り:{len(short_list)}")

    # ── スプレッドシートに記録 ──────────────────────────────────
    if daytrade_buy:
        write_to_spreadsheet(daytrade_buy, sheet_name="デイトレ買い")
    if short_list:
        write_to_spreadsheet(short_list, sheet_name="信用売り")

    # ── シグナルゼロなら送信しない ────────────────────────────
    if not buy_signals and not oshime_list and not daytrade_buy and not short_list:
        print("シグナルなし → メール送信なし")
        return

    subject = f"📈 kabu3 {time_str}"
    send_mail(subject, buy_signals, oshime_list, daytrade_buy, short_list)

if __name__ == "__main__":
    main()
