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
