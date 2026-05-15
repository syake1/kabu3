"""
auto_scan.py
GitHub Actionsから呼ばれる自動スキャン＋メール送信スクリプト
9時〜15時・1時間おきに実行
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json, os, smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── 設定 ──────────────────────────────────────────────────────
ALERT_TO   = "kamejirou1@gmail.com"
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "")

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

def sma(a):
    return sum(a) / len(a) if a else 0

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

            ma5  = float(last["MA_5"])
            ma25 = float(last["MA_25"])
            ma75 = float(last["MA_75"])
            price = float(last["Close"])
            rsi   = float(last["RSI"])
            macd_h = float(last["MACD_Hist"])
            macd_h_prev = float(prev["MACD_Hist"])
            stoch = float(last["Stoch_K"])
            bb_lower = float(last["BB_Lower"])
            bb_upper = float(last["BB_Upper"])

            uptrend  = price > ma75
            near_ma25 = abs(price - ma25) / ma25 < 0.08
            macd_gc  = float(prev["MACD"]) <= float(prev["MACD_Signal"]) and float(last["MACD"]) > float(last["MACD_Signal"])
            macd_up  = macd_h > macd_h_prev
            stoch_gc = float(prev["Stoch_K"]) <= float(prev["Stoch_D"]) and stoch > float(last["Stoch_D"])
            not_ob   = stoch < 70 and rsi < 65

            buy  = uptrend and near_ma25 and (macd_gc or (stoch_gc and stoch < 40)) and macd_up and not_ob
            sell = rsi > 70 or price >= bb_upper * 0.99

            results[tf_label] = "🟢" if buy else "🔴" if sell else "➖"
            results[f"RSI({tf_label})"]  = round(rsi, 1)
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

        near_ma25 = abs(price - ma25) / ma25 * 100 <= 5.0
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
        print("メール設定なし")
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

# ── メイン ─────────────────────────────────────────────────────
def main():
    now = datetime.now()
    time_str = now.strftime("%m/%d %H:%M")
    print(f"[{time_str}] 自動スキャン開始 対象:{len(TARGET)}銘柄")

    buy_signals  = []
    oshime_list  = []

    for i, (name, code) in enumerate(TARGET.items()):
        print(f"  {i+1}/{len(TARGET)} {name}", end="\r")
        try:
            tf_result = scan_multi_tf(code, name)
            buy_count = sum(1 for k in ["日足","1時間足","5分足"] if tf_result.get(k)=="🟢")
            ma25_bounce = tf_result.get("MA25反発", "") == "★"

            if buy_count >= 2:
                buy_signals.append({
                    "銘柄名": name, "コード": code,
                    "日足": tf_result.get("日足","❓"),
                    "1時間足": tf_result.get("1時間足","❓"),
                    "5分足": tf_result.get("5分足","❓"),
                    "一致数": buy_count,
                    "RSI": tf_result.get("RSI(日足)", "−"),
                })

            r = scan_oshime(code, name)
            if r:
                oshime_list.append(r)
        except Exception as e:
            pass

    print(f"\nマルチTF買い:{len(buy_signals)}銘柄  押し目:{len(oshime_list)}銘柄")

    if not buy_signals and not oshime_list:
        print("シグナルなし → メール送信なし")
        return

    # メール本文作成
    lines = [f"📈 自動スキャン結果  {time_str}", ""]

    if buy_signals:
        lines.append("=" * 40)
        lines.append("🔥 マルチTF買いシグナル（2TF以上一致）")
        lines.append("=" * 40)
        for r in sorted(buy_signals, key=lambda x: -x["一致数"]):
            star = "★★★" if r["一致数"]==3 else "★★☆"
            lines.append(f"【{star}】{r['銘柄名']} ({r['コード']})")
            lines.append(f"  日足:{r['日足']} 1h:{r['1時間足']} 5分:{r['5分足']}  RSI:{r['RSI']}")

    if oshime_list:
        lines.append("")
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

    body = "\n".join(lines)
    subject = f"📈 買いシグナル {time_str} ({len(buy_signals)+len(oshime_list)}件)"
    send_mail(subject, body)

if __name__ == "__main__":
    main()
