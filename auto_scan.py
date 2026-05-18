"""
auto_scan.py
GitHub Actionsから呼ばれる自動スキャン＋メール送信＋スプレッドシート記録
9時〜15時・1時間おきに実行
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json, os, smtplib, gspread
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.service_account import Credentials

# ── 設定 ──────────────────────────────────────────────────────
ALERT_TO   = "kamejirou1@gmail.com"
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "")

SPREADSHEET_ID  = os.environ.get("SPREADSHEET_ID", "")   # GitHub Secrets に登録
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")  # GitHub Secrets に登録

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

# ── マルチTFスキャン ────────────────────────────────────────────
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
                results[tf_label] = "❓"
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.dropna(how="all", inplace=True)
            df = calc_indicators(df)
            last = df.iloc[-1]
            prev = df.iloc[-2]

            ma5   = float(last["MA_5"])
            ma25  = float(last["MA_25"])
            ma75  = float(last["MA_75"])
            price = float(last["Close"])
            rsi   = float(last["RSI"])
            macd_h      = float(last["MACD_Hist"])
            macd_h_prev = float(prev["MACD_Hist"])
            stoch    = float(last["Stoch_K"])
            bb_lower = float(last["BB_Lower"])
            bb_upper = float(last["BB_Upper"])

            uptrend   = price > ma75
            near_ma25 = abs(price - ma25) / ma25 < 0.08
            macd_gc   = float(prev["MACD"]) <= float(prev["MACD_Signal"]) and float(last["MACD"]) > float(last["MACD_Signal"])
            macd_up   = macd_h > macd_h_prev
            stoch_gc  = float(prev["Stoch_K"]) <= float(prev["Stoch_D"]) and stoch > float(last["Stoch_D"])
            not_ob    = stoch < 70 and rsi < 65

            buy  = uptrend and near_ma25 and (macd_gc or (stoch_gc and stoch < 40)) and macd_up and not_ob
            sell = rsi > 70 or price >= bb_upper * 0.99

            results[tf_label] = "🟢" if buy else "🔴" if sell else "➖"
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

        last  = df.iloc[-1]
        prev  = df.iloc[-2]
        prev2 = df.iloc[-3]
        price    = float(last["Close"])
        ma5      = float(last["MA_5"])
        ma25     = float(last["MA_25"])
        ma75     = float(last["MA_75"])
        rsi      = float(last["RSI"])
        rsi_prev = float(prev["RSI"])
        bb_lower = float(last["BB_Lower"])
        macd_h   = float(last["MACD_Hist"])
        macd_hp  = float(prev["MACD_Hist"])

        if not (ma5 > ma25 > ma75):
            return None

        rsi_min5 = float(df["RSI"].iloc[-5:].min())
        if rsi_min5 > 32:
            return None
        if not (rsi > rsi_prev or rsi > float(prev2["RSI"])):
            return None

        bb_touch = any(float(df["Low"].iloc[i]) <= float(df["BB_Lower"].iloc[i]) * 1.01
                       for i in range(-5, 0))
        if not bb_touch:
            return None

        high52 = float(df["High"].max())
        if price >= high52 * 0.95:
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

# ── メール送信 ─────────────────────────────────────────────────
def send_mail(subject, body):
    if not GMAIL_USER or not GMAIL_PASS:
        print("メール設定なし（GMAIL_USER / GMAIL_PASS 未設定）")
        return
    try:
        msg = MIMEMultipart()
        msg["From"]    = GMAIL_USER
        msg["To"]      = ALERT_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, ALERT_TO, msg.as_string())
        print(f"✅ メール送信完了: {subject}")
    except Exception as e:
        print(f"❌ メール送信失敗: {e}")

# ── スプレッドシート書き込み ────────────────────────────────────
def write_to_spreadsheet(rows):
    """
    rows: list of dict
      {"日時", "銘柄名", "コード", "1時間足", "5分足", "RSI(1時間足)", "Stoch(1時間足)"}
    """
    if not SPREADSHEET_ID or not GOOGLE_CREDS_JSON:
        print("スプレッドシート設定なし（SPREADSHEET_ID / GOOGLE_CREDENTIALS 未設定）")
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
        sheet  = client.open_by_key(SPREADSHEET_ID).sheet1

        # ヘッダーが無ければ追加
        existing = sheet.get_all_values()
        if not existing:
            sheet.append_row(["日時", "銘柄名", "コード", "1時間足", "5分足",
                               "RSI(1h)", "Stoch(1h)"])

        for r in rows:
            sheet.append_row([
                r.get("日時", ""),
                r.get("銘柄名", ""),
                r.get("コード", ""),
                r.get("1時間足", ""),
                r.get("5分足", ""),
                r.get("RSI(1時間足)", ""),
                r.get("Stoch(1時間足)", ""),
            ])
        print(f"✅ スプレッドシート書き込み完了: {len(rows)}件")
    except Exception as e:
        print(f"❌ スプレッドシート書き込み失敗: {e}")

# ── メイン ─────────────────────────────────────────────────────
def main():
    now      = datetime.now()
    time_str = now.strftime("%m/%d %H:%M")
    print(f"[{time_str}] 自動スキャン開始 対象:{len(TARGET)}銘柄")

    buy_signals      = []   # マルチTF（2TF以上一致）
    oshime_list      = []   # 押し目買い
    daytrade_signals = []   # ⚡ デイトレ（1h＋5分 両方🟢）

    for i, (name, code) in enumerate(TARGET.items()):
        print(f"  {i+1}/{len(TARGET)} {name}", end="\r")
        try:
            tf_result = scan_multi_tf(code, name)

            h1  = tf_result.get("1時間足", "❓")
            m5  = tf_result.get("5分足",   "❓")
            day = tf_result.get("日足",    "❓")

            # マルチTF（2TF以上）
            buy_count = sum(1 for k in ["日足","1時間足","5分足"] if tf_result.get(k) == "🟢")
            if buy_count >= 2:
                buy_signals.append({
                    "銘柄名": name, "コード": code,
                    "日足": day, "1時間足": h1, "5分足": m5,
                    "一致数": buy_count,
                    "RSI": tf_result.get("RSI(日足)", "−"),
                })

            # ⚡ デイトレ（1時間足＋5分足が両方🟢）
            if h1 == "🟢" and m5 == "🟢":
                daytrade_signals.append({
                    "日時":       time_str,
                    "銘柄名":     name,
                    "コード":     code,
                    "1時間足":    h1,
                    "5分足":      m5,
                    "RSI(1時間足)":   tf_result.get("RSI(1時間足)", "−"),
                    "Stoch(1時間足)": tf_result.get("Stoch(1時間足)", "−"),
                })

            # 押し目
            r = scan_oshime(code, name)
            if r:
                oshime_list.append(r)

        except Exception:
            pass

    print(f"\nマルチTF買い:{len(buy_signals)}銘柄  押し目:{len(oshime_list)}銘柄  デイトレ:{len(daytrade_signals)}銘柄")

    # ── スプレッドシートに記録（デイトレのみ）──────────────────
    if daytrade_signals:
        write_to_spreadsheet(daytrade_signals)

    # ── シグナルゼロなら何もしない ────────────────────────────
    if not buy_signals and not oshime_list and not daytrade_signals:
        print("シグナルなし → メール送信なし")
        return

    # ── メール本文作成 ─────────────────────────────────────────
    lines = [f"📈 自動スキャン結果  {time_str}", ""]

    # ⚡ デイトレセクション
    if daytrade_signals:
        lines.append("=" * 40)
        lines.append("⚡ デイトレ買いシグナル（1h＋5分 両方🟢）")
        lines.append("=" * 40)
        for r in daytrade_signals:
            lines.append(f"【{r['銘柄名']}】 ({r['コード']})")
            lines.append(f"  1時間足:{r['1時間足']}  5分足:{r['5分足']}")
            lines.append(f"  RSI(1h):{r['RSI(1時間足)']}  Stoch(1h):{r['Stoch(1時間足)']}")
            lines.append(f"  検出時刻: {r['日時']}")
        lines.append("")

    # 🔥 マルチTFセクション
    if buy_signals:
        lines.append("=" * 40)
        lines.append("🔥 マルチTF買いシグナル（2TF以上一致）")
        lines.append("=" * 40)
        for r in sorted(buy_signals, key=lambda x: -x["一致数"]):
            star = "★★★" if r["一致数"] == 3 else "★★☆"
            lines.append(f"【{star}】{r['銘柄名']} ({r['コード']})")
            lines.append(f"  日足:{r['日足']} 1h:{r['1時間足']} 5分:{r['5分足']}  RSI:{r['RSI']}")
        lines.append("")

    # 📉 押し目セクション
    if oshime_list:
        lines.append("=" * 40)
        lines.append("📉 押し目買いシグナル（RSI売られすぎ＋BB下限）")
        lines.append("=" * 40)
        for r in oshime_list:
            lines.append(f"{r['銘柄名']} ({r['コード']})")
            lines.append(f"  株価:¥{r['株価']:,}  RSI:{r['RSI']}")
            lines.append(f"  エントリー:¥{r['エントリー']:,}  損切り:¥{r['損切り']:,}  利確:¥{r['利確目標']:,}")
            lines.append(f"  根拠:{r['根拠']}")
        lines.append("")

    lines.append("⚠️ 投資判断はご自身の責任でお願いします。")

    body    = "\n".join(lines)
    total   = len(buy_signals) + len(oshime_list) + len(daytrade_signals)
    subject = f"📈 買いシグナル {time_str} ({total}件)"
    send_mail(subject, body)

if __name__ == "__main__":
    main()
