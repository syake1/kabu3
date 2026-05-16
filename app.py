import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json, os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="kabu3 Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 8px 10px 20px 10px !important; max-width: 100% !important; }
.stButton > button { min-height: 48px; font-size: 15px; border-radius: 10px; font-weight: bold; }
[data-testid="stMetric"] {
    background: #111827; border-radius: 10px;
    padding: 10px 8px; border: 1px solid #1e293b; text-align: center;
}
[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
[data-testid="stTabs"] [role="tab"] { font-size: 13px; padding: 6px 10px; }
#pwa-bar {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: #0a0e1a; border-top: 1px solid rgba(0,212,170,0.3);
    padding: 10px 16px; display: flex; align-items: center;
    justify-content: space-between; z-index: 99999; font-family: sans-serif;
}
#pwa-bar span { color: #94a3b8; font-size: 13px; }
#pwa-bar button { background: #00d4aa; color: #0a0e1a; border: none;
    border-radius: 20px; padding: 8px 18px; font-size: 13px; font-weight: bold; cursor: pointer; }
#pwa-bar .pwa-close { background: none; color: #94a3b8; border: none;
    font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 6px; }
</style>
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="kabu3 Pro">
<meta name="theme-color" content="#00d4aa">
<div id="pwa-bar">
  <span>📲 ホーム画面に追加できます</span>
  <button onclick="installPWA()">追加する</button>
  <button class="pwa-close" onclick="document.getElementById('pwa-bar').style.display='none'">✕</button>
</div>
<script>
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredPrompt = e; });
function installPWA() {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(() => { deferredPrompt = null; document.getElementById('pwa-bar').style.display='none'; });
    } else {
        const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
        alert(isIOS ? '① Safariで開く\n② 共有ボタン（□↑）\n③ ホーム画面に追加' : '① Chromeで開く\n② メニュー（⋮）\n③ ホーム画面に追加');
    }
}
</script>
""", unsafe_allow_html=True)

# ── ファイルパス ──────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
TICKER_FILE   = os.path.join(BASE_DIR, "kabu3_tickers.json")
TRACKING_FILE = os.path.join(BASE_DIR, "kabu3_tracking.csv")

DEFAULT_TICKERS = {
    "半導体・電子部品": {
        "東京エレクトロン":"8035.T","アドバンテスト":"6857.T","レーザーテック":"6920.T",
        "ソシオネクスト":"6526.T","SCREENホールディングス":"7735.T","ルネサスエレクトロニクス":"6723.T",
        "ローム":"6963.T","イビデン":"4062.T","日東電工":"6988.T","太陽誘電":"6976.T",
        "浜松ホトニクス":"6965.T","ディスコ":"6146.T","信越化学工業":"4063.T",
    },
    "電機・精密": {
        "ソニーグループ":"6758.T","キーエンス":"6861.T","日立製作所":"6501.T",
        "ファナック":"6954.T","三菱電機":"6503.T","富士電機":"6504.T",
        "安川電機":"6506.T","オムロン":"6645.T","TDK":"6762.T","村田製作所":"6981.T",
        "京セラ":"6971.T","HOYA":"7741.T","キヤノン":"7751.T","リコー":"7752.T",
        "富士フイルム":"4901.T","NEC":"6701.T","富士通":"6702.T","横河電機":"6841.T",
        "ニコン":"7731.T","オリンパス":"7733.T","シスメックス":"6869.T",
        "マブチモーター":"6592.T","ミネベアミツミ":"6479.T",
    },
    "自動車・部品": {
        "トヨタ自動車":"7203.T","ホンダ":"7267.T","デンソー":"6902.T",
        "スズキ":"7269.T","SUBARU":"7270.T","マツダ":"7261.T","ヤマハ発動機":"7272.T",
        "日産自動車":"7201.T","三菱自動車":"7211.T","アイシン":"7259.T",
        "ジェイテクト":"6473.T","NTN":"6472.T","ブリヂストン":"5108.T",
        "横浜ゴム":"5101.T","日本精工":"6471.T",
    },
    "機械": {
        "小松製作所":"6301.T","クボタ":"6326.T","ダイキン工業":"6367.T",
        "三菱重工業":"7011.T","IHI":"7013.T","川崎重工業":"7012.T",
        "日立建機":"6305.T","荏原製作所":"6361.T","ダイフク":"6383.T","THK":"6481.T",
        "AIRMAN":"6364.T","竹内製作所":"6432.T","住友重機械工業":"6302.T",
        "DMG森精機":"6141.T","椿本チエイン":"6371.T","タダノ":"6395.T",
        "フジテック":"6406.T","SMC":"6273.T","アマノ":"6436.T",
    },
    "建設": {
        "大成建設":"1801.T","大林組":"1802.T","清水建設":"1803.T","鹿島建設":"1812.T",
        "長谷工コーポレーション":"1808.T","西松建設":"1820.T","五洋建設":"1893.T",
        "東急建設":"1720.T","不動テトラ":"1813.T","前田建設工業":"1824.T",
        "日揮HD":"1963.T","積水ハウス":"1928.T","大和ハウス工業":"1925.T",
        "住友林業":"1911.T","きんでん":"1944.T","エクシオグループ":"1951.T",
        "奥村組":"1833.T","東鉄工業":"1835.T","九電工":"1959.T","コムシスHD":"1721.T",
        "高松建設":"1762.T","東洋建設":"1890.T","若築建設":"1888.T",
    },
    "銀行": {
        "三菱UFJ":"8306.T","三井住友FG":"8316.T","みずほFG":"8411.T",
        "東京きらぼしFG":"7173.T","ふくおかFG":"8354.T","コンコルディアFG":"7186.T",
        "ほくほくFG":"8377.T","山口FG":"8379.T","伊予銀行":"8385.T",
        "阿波銀行":"8388.T","百五銀行":"8368.T","七十七銀行":"8341.T",
        "八十二銀行":"8359.T","南都銀行":"8367.T","西日本FH":"7189.T",
    },
    "保険・証券・金融": {
        "東京海上HD":"8766.T","MS&ADインシュアランスG":"8725.T","第一生命HD":"8750.T",
        "オリックス":"8591.T","全国保証":"7164.T","プレミアグループ":"7199.T",
        "SBIホールディングス":"8473.T","大和証券G本社":"8601.T",
        "野村HD":"8604.T","日本取引所G":"8697.T",
    },
    "通信・IT": {
        "ソフトバンクG":"9984.T","NTT":"9432.T","KDDI":"9433.T","ソフトバンク":"9434.T",
        "リクルートHD":"6098.T","野村総合研究所":"4307.T","デジタルアーツ":"2326.T",
        "インテリジェントウェイブ":"4847.T","クレスコ":"4674.T","エン・ジャパン":"4849.T",
        "サイバーエージェント":"4751.T","楽天グループ":"4755.T","TIS":"3626.T",
        "SCSK":"9719.T","NTTデータ":"9613.T","ラクス":"3923.T","Sansan":"4443.T",
    },
    "商社": {
        "三菱商事":"8058.T","伊藤忠商事":"8001.T","三井物産":"8031.T",
        "丸紅":"8002.T","住友商事":"8053.T","豊田通商":"8015.T",
        "サンワテクノス":"8137.T","稲畑産業":"8098.T","双日":"2768.T",
        "ミスミグループ本社":"9962.T","モノタロウ":"3064.T",
    },
    "化学・素材": {
        "三菱ケミカルG":"4188.T","住友化学":"4005.T","花王":"4452.T",
        "エア・ウォーター":"4088.T","住友ベークライト":"4203.T",
        "日本製鉄":"5401.T","JFEホールディングス":"5411.T","神戸製鋼所":"5406.T",
        "住友金属鉱山":"5713.T","三井化学":"4183.T","東ソー":"4042.T",
        "旭化成":"3407.T","帝人":"3401.T","東レ":"3402.T","積水化学工業":"4204.T",
        "日油":"4403.T","DIC":"4631.T",
    },
    "医薬品・ヘルスケア": {
        "武田薬品工業":"4502.T","アステラス製薬":"4503.T","中外製薬":"4519.T",
        "第一三共":"4568.T","塩野義製薬":"4507.T","エーザイ":"4523.T",
        "小野薬品工業":"4528.T","大塚HD":"4578.T","ロート製薬":"4527.T",
        "テルモ":"4543.T","富士フイルム":"4901.T","ツムラ":"4540.T",
    },
    "小売": {
        "ファーストリテイリング":"9983.T","セブン&アイHD":"3382.T","イオン":"8267.T",
        "三越伊勢丹HD":"3099.T","高島屋":"8233.T","丸井グループ":"8252.T",
        "ニトリHD":"9843.T","良品計画":"7453.T","しまむら":"8227.T",
        "ゲオHD":"2681.T","スクロール":"8005.T","ヤマダHD":"9831.T",
        "ビックカメラ":"3048.T","カッパ・クリエイト":"7421.T","ユナイテッドアローズ":"7606.T",
        "アダストリア":"2685.T","青山商事":"8219.T",
    },
    "食品・飲料": {
        "明治HD":"2269.T","アサヒグループHD":"2502.T","キリンHD":"2503.T",
        "日本たばこ産業":"2914.T","キッコーマン":"2801.T","ハウス食品G":"2810.T",
        "日清食品HD":"2897.T","日本ハム":"2282.T","ニチレイ":"2871.T",
        "味の素":"2802.T","カルビー":"2229.T","日清製粉G":"2002.T",
        "ヤクルト本社":"2267.T","サッポロHD":"2501.T",
    },
    "不動産": {
        "三井不動産":"8801.T","三菱地所":"8802.T","住友不動産":"8830.T",
        "ヒューリック":"3003.T","東京建物":"8804.T","スターツコーポレーション":"8850.T",
        "野村不動産HD":"3231.T","大東建託":"1878.T","オープンハウスG":"3288.T",
    },
    "海運・空運・物流": {
        "日本郵船":"9101.T","商船三井":"9104.T","川崎汽船":"9107.T",
        "澁澤倉庫":"9304.T","ヤマトHD":"9064.T","SGホールディングス":"9143.T",
        "日本通運":"9062.T","ANA HD":"9202.T","JAL":"9201.T",
    },
    "陸運・インフラ": {
        "東日本旅客鉄道":"9020.T","東海旅客鉄道":"9022.T","西日本旅客鉄道":"9021.T",
        "東京急行電鉄":"9005.T","京浜急行電鉄":"9006.T","阪急阪神HD":"9042.T",
        "東京電力HD":"9501.T","関西電力":"9503.T","東京ガス":"9531.T","大阪ガス":"9532.T",
    },
    "サービス・エンタメ": {
        "オリエンタルランド":"4661.T","東宝":"9602.T","任天堂":"7974.T",
        "バンダイナムコHD":"7832.T","カプコン":"9697.T","コナミG":"9766.T",
        "吉野家HD":"9861.T","マクドナルド":"2702.T","ゼンショーHD":"7550.T",
        "トリドールHD":"3397.T","パーソルHD":"2181.T",
    },
    "為替・指数": {
        "USDJPY":"USDJPY=X","EURJPY":"EURJPY=X","AUDJPY":"AUDJPY=X",
    },
}

if os.path.exists(TICKER_FILE):
    with open(TICKER_FILE, "r", encoding="utf-8") as f:
        file_tickers = json.load(f)
else:
    file_tickers = DEFAULT_TICKERS

if 'tickers' not in st.session_state:
    st.session_state['tickers'] = file_tickers

def save_tickers():
    try:
        with open(TICKER_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state['tickers'], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ── 勝率トラッキング ──────────────────────────────────────────
def load_tracking():
    if not os.path.exists(TRACKING_FILE):
        return pd.DataFrame(columns=["日付","コード","銘柄名","種別","記録時株価","3日後","5日後","3日騰落率","勝敗"])
    return pd.read_csv(TRACKING_FILE, encoding="utf-8-sig")

def save_tracking(df):
    try:
        df.to_csv(TRACKING_FILE, index=False, encoding="utf-8-sig")
    except Exception:
        pass


# ╔══════════════════════════════════════════════════════════╗
# ║   メール送信（Gmailアプリパスワード使用）                       ║
# ╚══════════════════════════════════════════════════════════╝
ALERT_TO = "kamejirou1@gmail.com"

def send_buy_alert(signal_rows, oshime_rows):
    """買いシグナル・押し目買いをメールで通知"""
    try:
        gmail_user = st.secrets["gmail_user"]
        gmail_pass = st.secrets["gmail_pass"]
    except Exception:
        return False, "Secretsが未設定です"

    if not signal_rows and not oshime_rows:
        return False, "通知対象なし"

    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    lines = ["📈 株式買いシグナル通知  " + today, ""]

    if signal_rows:
        lines.append("=" * 38)
        lines.append("🔥 マルチTF買いシグナル")
        lines.append("=" * 38)
        for r in signal_rows:
            grade  = r.get("強度", "")
            name   = r.get("銘柄名", "")
            code   = r.get("コード", "")
            nichi  = r.get("日足", "")
            ichi   = r.get("1時間足", "")
            go     = r.get("5分足", "")
            rsi    = r.get("RSI(日足)", "−")
            ma25   = r.get("MA25反発", "")
            lines.append("【" + grade + "】" + name + " (" + code + ")")
            lines.append("  日足:" + str(nichi) + " 1h:" + str(ichi) + " 5分:" + str(go))
            lines.append("  RSI:" + str(rsi) + "  " + str(ma25))

    if oshime_rows:
        lines.append("")
        lines.append("=" * 38)
        lines.append("📉 押し目買いシグナル")
        lines.append("=" * 38)
        for r in oshime_rows:
            hantei  = r.get("判定", "")
            name    = r.get("銘柄名", "")
            code    = r.get("コード", "")
            kakaku  = r.get("株価", 0)
            oshime  = r.get("押し目幅", "")
            support = r.get("サポート", "")
            entry   = r.get("エントリー", 0)
            stop    = r.get("損切り", 0)
            target  = r.get("利確目標", 0)
            reason  = r.get("根拠", "")
            lines.append("【" + hantei + "】" + name + " (" + code + ")")
            lines.append("  株価:¥" + str(kakaku) + "  押し目:" + oshime + "  サポート:" + support)
            lines.append("  エントリー:¥" + str(entry) + "  損切り:¥" + str(stop) + "  利確:¥" + str(target))
            lines.append("  根拠: " + reason)

    lines.append("")
    lines.append("⚠️ 投資判断はご自身の責任でお願いします。")
    body = "\n".join(lines)

    try:
        msg = MIMEMultipart()
        msg["From"]    = gmail_user
        msg["To"]      = ALERT_TO
        msg["Subject"] = "📈 買いシグナル " + today
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, ALERT_TO, msg.as_string())
        return True, str(len(signal_rows) + len(oshime_rows)) + "件のシグナルを送信しました"
    except Exception as e:
        return False, str(e)

def get_current_price(code):
    try:
        df = yf.download(code, period="2d", interval="1d", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            return round(float(df["Close"].dropna().iloc[-1]), 1)
    except Exception:
        pass
    return None

def get_price_at(code, target_date):
    try:
        start = target_date - timedelta(days=2)
        end   = target_date + timedelta(days=3)
        df = yf.download(code, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), interval="1d", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            return round(float(df["Close"].dropna().iloc[-1]), 1)
    except Exception:
        pass
    return None

def update_tracking():
    df = load_tracking()
    if df.empty:
        return df
    today = datetime.now()
    for i, row in df.iterrows():
        try:
            rec_date = datetime.strptime(str(row["日付"]), "%Y-%m-%d")
            diff = (today - rec_date).days
            code = str(row["コード"])
            entry = float(row["記録時株価"]) if row["記録時株価"] else None
            if not entry:
                continue
            if diff >= 3 and not row["3日後"]:
                p = get_price_at(code, rec_date + timedelta(days=3))
                if p:
                    df.at[i, "3日後"] = p
                    pct = (p - entry) / entry * 100
                    df.at[i, "3日騰落率"] = round(pct, 2)
                    df.at[i, "勝敗"] = "✅ 勝" if pct >= 3 else "❌ 負" if pct <= -3 else "△ 引分"
            if diff >= 5 and not row["5日後"]:
                p = get_price_at(code, rec_date + timedelta(days=5))
                if p:
                    df.at[i, "5日後"] = p
        except Exception:
            pass
    save_tracking(df)
    return df

# ── 指標計算 ──────────────────────────────────────────────────
def calculate_indicators(df, bb_std=2.0):
    c = df['Close']
    for w in [5, 25, 75]:
        df[f'MA_{w}'] = c.rolling(w).mean()
    df['BB_Mid']   = c.rolling(20).mean()
    df['BB_Std']   = c.rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + df['BB_Std'] * bb_std
    df['BB_Lower'] = df['BB_Mid'] - df['BB_Std'] * bb_std
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df['MACD']        = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist']   = df['MACD'] - df['MACD_Signal']
    delta = c.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14).mean()
    loss  = -delta.clip(upper=0).ewm(alpha=1/14, min_periods=14).mean()
    df['RSI'] = 100 - (100 / (1 + gain / loss))
    low14  = df['Low'].rolling(14).min()
    high14 = df['High'].rolling(14).max()
    df['Stoch_K'] = 100 * (c - low14) / (high14 - low14)
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
    hd  = df['High'] - df['High'].shift(1)
    ld  = df['Low'].shift(1) - df['Low']
    pdm = pd.Series(np.where((hd > ld) & (hd > 0), hd, 0), index=df.index)
    mdm = pd.Series(np.where((ld > hd) & (ld > 0), ld, 0), index=df.index)
    tr  = pd.concat([df['High']-df['Low'],
                     (df['High']-df['Close'].shift(1)).abs(),
                     (df['Low']-df['Close'].shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()
    df['Plus_DI']  = 100 * pdm.ewm(alpha=1/14, adjust=False).mean() / atr
    df['Minus_DI'] = 100 * mdm.ewm(alpha=1/14, adjust=False).mean() / atr
    dx  = 100 * (df['Plus_DI'] - df['Minus_DI']).abs() / (df['Plus_DI'] + df['Minus_DI'])
    df['ADX'] = dx.ewm(alpha=1/14, adjust=False).mean()
    df['MA25_Touch']  = (df['Low'] - df['MA_25']).abs() / df['MA_25'] < 0.03
    df['MA25_Bounce'] = df['MA25_Touch'].rolling(5).max().fillna(False).astype(bool) & (c > df['MA_25'])
    return df

# ╔══════════════════════════════════════════════════════════╗
# ║   押し目買いスキャナー（新機能）                              ║
# ╚══════════════════════════════════════════════════════════╝
def scan_oshime(code, name, pullback_min=3.0, pullback_max=15.0, near_ma_pct=3.0):
    """
    本当の押し目買い判定（高値圏除外版）
    ① 上昇トレンド: MA5 > MA25 > MA75
    ② RSIが30以下まで下落 → 売られすぎ圏に到達
    ③ RSIが30から反発してきた
    ④ ボリンジャーバンド -2σ（下限）に株価がタッチ
    ⑤ 25日線付近にいる
    ⑥ MACDヒストグラムが底打ち反転
    """
    try:
        df = yf.download(code, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 80:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how='all', inplace=True)
        df = calculate_indicators(df)

        last      = df.iloc[-1]
        prev      = df.iloc[-2]
        prev2     = df.iloc[-3]

        price     = float(last['Close'])
        ma5       = float(last['MA_5'])
        ma25      = float(last['MA_25'])
        ma75      = float(last['MA_75'])
        rsi       = float(last['RSI'])
        rsi_prev  = float(prev['RSI'])
        rsi_prev2 = float(prev2['RSI'])
        bb_lower  = float(last['BB_Lower'])
        bb_upper  = float(last['BB_Upper'])
        macd_hist      = float(last['MACD_Hist'])
        macd_hist_prev = float(prev['MACD_Hist'])
        vol      = float(df['Volume'].iloc[-1])
        vol_avg  = float(df['Volume'].iloc[-20:].mean())

        # ① 上昇トレンド確認（MA5 > MA25 > MA75）
        uptrend = ma5 > ma25 > ma75
        if not uptrend:
            return None

        # ② RSIが直近5日以内に30以下を記録したか
        rsi_min5 = float(df['RSI'].iloc[-5:].min())
        rsi_touched_oversold = rsi_min5 <= 32
        if not rsi_touched_oversold:
            return None

        # ③ RSIが反発中（今日 > 昨日 or 一昨日から上向き）
        rsi_rebounding = rsi > rsi_prev or rsi > rsi_prev2
        if not rsi_rebounding:
            return None

        # ④ ボリンジャーバンド下限タッチ（直近5日で株価が-2σ以下に触れた）
        bb_touched = False
        for i in range(-5, 0):
            low_i  = float(df['Low'].iloc[i])
            bb_l_i = float(df['BB_Lower'].iloc[i])
            if low_i <= bb_l_i * 1.01:
                bb_touched = True
                break
        if not bb_touched:
            return None

        # ⑤ 現在値が25日線付近（±5%以内）
        near_ma25 = abs(price - ma25) / ma25 * 100 <= 5.0
        near_ma5  = abs(price - ma5)  / ma5  * 100 <= 3.0
        support_level = "MA25" if near_ma25 else ("MA5" if near_ma5 else "BB下限")

        # ⑥ MACDヒストグラム底打ち
        macd_bottom = macd_hist > macd_hist_prev

        # 高値圏チェック（52週高値の95%以上なら除外）
        high52 = float(df['High'].iloc[-252:].max()) if len(df) >= 252 else float(df['High'].max())
        if price >= high52 * 0.95:
            return None

        # スコア計算
        score = 0
        reasons = []

        score += 4; reasons.append("RSI売られすぎ圏タッチ")
        score += 3; reasons.append("BB下限タッチ")
        if rsi_rebounding:   score += 2; reasons.append("RSI反発中")
        if macd_bottom:      score += 2; reasons.append("MACD底打ち")
        if near_ma25:        score += 2; reasons.append("MA25付近")
        if vol > vol_avg * 1.5: score += 1; reasons.append("出来高急増")

        grade = "🟢 絶好の押し目" if score >= 10 else                 "🟡 押し目候補"   if score >= 7  else                 "⬜ 参考"

        high20 = float(df['High'].iloc[-20:].max())
        entry  = round(price, 1)
        stop   = round(bb_lower * 0.98, 1)
        target = round(ma25 * 1.10, 1)

        return {
            "銘柄名":     name,
            "コード":     code,
            "株価":       round(price, 1),
            "BB下限":     round(bb_lower, 1),
            "RSI":        round(rsi, 1),
            "RSI最小":    round(rsi_min5, 1),
            "サポート":   support_level,
            "出来高比":   str(round(vol/vol_avg, 1)) + "x",
            "MACDボトム": "✓" if macd_bottom else "－",
            "スコア":     score,
            "判定":       grade,
            "エントリー": entry,
            "損切り":     stop,
            "利確目標":   target,
            "根拠":       " / ".join(reasons),
            "押し目幅":   str(round((high20 - price) / high20 * 100, 1)) + "%",
            "直近高値":   round(high20, 1),
        }
    except Exception as e:
        return None


def scan_oshime_1h(code, name):
    """1時間足 デイトレ押し目買い判定"""
    try:
        df = yf.download(code, period="30d", interval="1h", progress=False)
        if df.empty or len(df) < 50:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how='all', inplace=True)
        df = calculate_indicators(df)

        last  = df.iloc[-1]
        prev  = df.iloc[-2]
        price = float(last['Close'])
        ma25  = float(last['MA_25'])
        rsi   = float(last['RSI'])
        rsi_prev = float(prev['RSI'])
        bb_lower = float(last['BB_Lower'])
        macd_hist      = float(last['MACD_Hist'])
        macd_hist_prev = float(prev['MACD_Hist'])

        # RSIが35以下タッチ → 反発中
        rsi_min = float(df['RSI'].iloc[-8:].min())
        if rsi_min > 35:
            return None
        if not (rsi > rsi_prev):
            return None

        # BB下限タッチ（直近8本）
        bb_touch = any(float(df['Low'].iloc[i]) <= float(df['BB_Lower'].iloc[i]) * 1.01
                       for i in range(-8, 0))
        if not bb_touch:
            return None

        macd_bottom = macd_hist > macd_hist_prev
        near_ma25   = abs(price - ma25) / ma25 * 100 <= 5.0

        score = 4
        reasons = ["RSI売られすぎ(1h)", "BB下限(1h)"]
        if macd_bottom: score += 2; reasons.append("MACD底打ち(1h)")
        if near_ma25:   score += 2; reasons.append("MA25付近(1h)")
        if rsi < 32:    score += 1; reasons.append("RSI深め")

        grade = "🟢 絶好(1h)" if score >= 7 else "🟡 候補(1h)"

        return {
            "銘柄名": name, "コード": code, "時間軸": "1時間足",
            "株価": round(price, 1), "RSI": round(rsi, 1),
            "RSI最小": round(rsi_min, 1), "BB下限": round(bb_lower, 1),
            "サポート": "MA25" if near_ma25 else "BB下限",
            "MACDボトム": "✓" if macd_bottom else "－",
            "スコア": score, "判定": grade,
            "エントリー": round(price, 1),
            "損切り": round(bb_lower * 0.98, 1),
            "利確目標": round(price * 1.03, 1),
            "根拠": " / ".join(reasons),
        }
    except Exception:
        return None


def scan_oshime_5m(code, name):
    """5分足 デイトレ押し目買い判定"""
    try:
        df = yf.download(code, period="5d", interval="5m", progress=False)
        if df.empty or len(df) < 50:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.dropna(how='all', inplace=True)
        df = calculate_indicators(df)

        last  = df.iloc[-1]
        prev  = df.iloc[-2]
        price = float(last['Close'])
        ma25  = float(last['MA_25'])
        rsi   = float(last['RSI'])
        rsi_prev = float(prev['RSI'])
        bb_lower = float(last['BB_Lower'])
        macd_hist      = float(last['MACD_Hist'])
        macd_hist_prev = float(prev['MACD_Hist'])

        # RSIが30以下タッチ → 反発中
        rsi_min = float(df['RSI'].iloc[-12:].min())
        if rsi_min > 32:
            return None
        if not (rsi > rsi_prev):
            return None

        # BB下限タッチ（直近12本）
        bb_touch = any(float(df['Low'].iloc[i]) <= float(df['BB_Lower'].iloc[i]) * 1.01
                       for i in range(-12, 0))
        if not bb_touch:
            return None

        macd_bottom = macd_hist > macd_hist_prev
        near_ma25   = abs(price - ma25) / ma25 * 100 <= 3.0

        score = 4
        reasons = ["RSI売られすぎ(5m)", "BB下限(5m)"]
        if macd_bottom: score += 2; reasons.append("MACD底打ち(5m)")
        if near_ma25:   score += 2; reasons.append("MA25付近(5m)")

        grade = "🟢 絶好(5m)" if score >= 7 else "🟡 候補(5m)"

        return {
            "銘柄名": name, "コード": code, "時間軸": "5分足",
            "株価": round(price, 1), "RSI": round(rsi, 1),
            "RSI最小": round(rsi_min, 1), "BB下限": round(bb_lower, 1),
            "サポート": "MA25" if near_ma25 else "BB下限",
            "MACDボトム": "✓" if macd_bottom else "－",
            "スコア": score, "判定": grade,
            "エントリー": round(price, 1),
            "損切り": round(bb_lower * 0.99, 1),
            "利確目標": round(price * 1.015, 1),
            "根拠": " / ".join(reasons),
        }
    except Exception:
        return None

def detect_signals(df, rsi_ob=70, rsi_os=30, sensitivity="標準",
                   trend_filter=True, dmi_filter=False, bb_std=2.0):
    df['Buy_Signal']  = False
    df['Sell_Signal'] = False
    if len(df) < 50:
        return df
    uptrend  = df['Close'] > df['MA_75'] if trend_filter else pd.Series(True, index=df.index)
    dmi_up   = (df['Plus_DI'] > df['Minus_DI']) & (df['ADX'] > 20) if dmi_filter else pd.Series(True, index=df.index)
    dmi_down = (df['Minus_DI'] > df['Plus_DI']) & (df['ADX'] > 20) if dmi_filter else pd.Series(True, index=df.index)
    pm  = df['MACD'].shift(1); ps  = df['MACD_Signal'].shift(1)
    ph  = df['MACD_Hist'].shift(1)
    psk = df['Stoch_K'].shift(1); psd = df['Stoch_D'].shift(1)
    macd_gc  = (pm <= ps) & (df['MACD'] > df['MACD_Signal'])
    macd_dc  = (pm >= ps) & (df['MACD'] < df['MACD_Signal'])
    macd_up  = df['MACD_Hist'] > ph
    macd_dn  = df['MACD_Hist'] < ph
    stoch_gc = (psk <= psd) & (df['Stoch_K'] > df['Stoch_D'])
    stoch_dc = (psk >= psd) & (df['Stoch_K'] < df['Stoch_D'])
    pr  = df['RSI'].shift(1)
    rsi_reb  = (pr <= rsi_os + 10) & (df['RSI'] > pr)
    rsi_drp  = (pr >= rsi_ob - 10) & (df['RSI'] < pr)
    if sensitivity == "敏感":
        not_ob = (df['Stoch_K'] < 70) & (df['RSI'] < 65)
        df.loc[uptrend & dmi_up &
               (macd_gc | (stoch_gc & (df['Stoch_K'] < 50)) | rsi_reb) &
               ~macd_dc & not_ob, 'Buy_Signal'] = True
        df.loc[dmi_down &
               (macd_dc | (stoch_dc & (df['Stoch_K'] > 50)) | rsi_drp) &
               ~macd_gc & macd_dn, 'Sell_Signal'] = True
    else:
        near25 = (df['Close'] - df['MA_25']).abs() / df['MA_25'] < 0.08
        not_ob = (df['Stoch_K'] < 70) & (df['RSI'] < 65)
        df.loc[uptrend & dmi_up & near25 &
               (macd_gc | (stoch_gc & (df['Stoch_K'] < 40))) &
               ~macd_dc & macd_up & not_ob, 'Buy_Signal'] = True
        touch_ub = df['High'] >= df['BB_Upper']
        df.loc[dmi_down &
               ((df['RSI'] > rsi_ob) | touch_ub | (stoch_dc & (df['Stoch_K'] > 70))) &
               ~macd_gc & macd_dn, 'Sell_Signal'] = True
    return df

@st.cache_data(ttl=180)
def load_data(ticker, period, interval):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.dropna(how='all', inplace=True)
            if pd.api.types.is_datetime64_any_dtype(df.index):
                df.index = (df.index.tz_localize('Asia/Tokyo')
                            if df.index.tz is None
                            else df.index.tz_convert('Asia/Tokyo'))
        return df
    except Exception:
        return pd.DataFrame()

def get_signal_time(df, signal_col, tf):
    """シグナルが最後に発生したローソク足の時刻を返す"""
    try:
        buy_rows = df[df[signal_col] == True]
        if buy_rows.empty:
            return None
        last_signal_time = buy_rows.index[-1]
        # 日足は日付だけ、1h・5分は時刻も表示
        if tf == "1d":
            return last_signal_time.strftime("%m/%d")
        else:
            # JSTに変換
            try:
                t = last_signal_time.tz_convert("Asia/Tokyo")
            except Exception:
                t = last_signal_time
            return t.strftime("%m/%d %H:%M")
    except Exception:
        return None


def scan_one(code, tf, period, rsi_ob, rsi_os, sensitivity, trend_filter, dmi_filter, bb_std):
    df = load_data(code, period, tf)
    if df.empty or len(df) < 50:
        return "❓", None, None, None, False, None
    df = calculate_indicators(df, bb_std=bb_std)
    df = detect_signals(df, rsi_ob=rsi_ob, rsi_os=rsi_os, sensitivity=sensitivity,
                        trend_filter=trend_filter, dmi_filter=dmi_filter, bb_std=bb_std)
    last      = df.iloc[-1]
    rsi_val   = round(float(last['RSI']),    1) if not np.isnan(last['RSI'])     else None
    stoch_val = round(float(last['Stoch_K']),1) if not np.isnan(last['Stoch_K']) else None
    adx_val   = round(float(last['ADX']),    1) if not np.isnan(last['ADX'])     else None
    ma25_b    = bool(last['MA25_Bounce'])
    if last['Buy_Signal']:
        sig_time = get_signal_time(df, 'Buy_Signal', tf)
        return "🟢", rsi_val, stoch_val, adx_val, ma25_b, sig_time
    if last['Sell_Signal']:
        sig_time = get_signal_time(df, 'Sell_Signal', tf)
        return "🔴", rsi_val, stoch_val, adx_val, ma25_b, sig_time
    return "➖", rsi_val, stoch_val, adx_val, ma25_b, None

TF_CONFIG = {
    "日足":    {"tf": "1d",  "period": "1y"},
    "1時間足": {"tf": "1h",  "period": "3mo"},
    "5分足":   {"tf": "5m",  "period": "5d"},
}

# ── チャート ──────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_chart_data(code):
    df = load_data(code, "6mo", "1d")
    if df.empty:
        return None
    df = calculate_indicators(df)
    df = detect_signals(df)
    return df

def draw_chart(code, name, entry=None, stop=None, target=None):
    df = get_chart_data(code)
    if df is None or df.empty:
        st.warning("チャートデータを取得できませんでした")
        return
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03,
        subplot_titles=[f"{name} ({code})", "MACD", "RSI"])
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="株価", increasing_line_color='#ef4444', decreasing_line_color='#3b82f6'), row=1, col=1)
    for col, color, label in [("MA_5","#facc15","MA5"), ("MA_25","#00d4aa","MA25"), ("MA_75","#a78bfa","MA75")]:
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col], name=label,
                line=dict(color=color, width=1.5)), row=1, col=1)
    # 押し目ライン
    if entry:
        fig.add_hline(y=entry,  line_color='#00d4aa', line_dash='dash', annotation_text=f"エントリー {entry}", row=1, col=1)
    if stop:
        fig.add_hline(y=stop,   line_color='#ef4444', line_dash='dash', annotation_text=f"損切り {stop}", row=1, col=1)
    if target:
        fig.add_hline(y=target, line_color='#facc15', line_dash='dash', annotation_text=f"利確 {target}", row=1, col=1)
    buy_pts = df[df['Buy_Signal']]
    if not buy_pts.empty:
        fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.99, mode='markers',
            marker=dict(symbol='triangle-up', size=12, color='#00d4aa'), name='買いシグナル'), row=1, col=1)
    hist_colors = ['#ef4444' if v < 0 else '#00d4aa' for v in df['MACD_Hist'].fillna(0)]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACDヒスト",
        marker_color=hist_colors, opacity=0.7), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'],        name="MACD",   line=dict(color='#60a5fa', width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], name="シグナル", line=dict(color='#f97316', width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI",
        line=dict(color='#a78bfa', width=1.5)), row=3, col=1)
    fig.add_hline(y=70, line_color='rgba(239,68,68,0.4)',  line_dash='dash', row=3, col=1)
    fig.add_hline(y=30, line_color='rgba(0,212,170,0.4)', line_dash='dash', row=3, col=1)
    fig.update_layout(height=600, paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        font=dict(color='#e6edf3', size=11),
        legend=dict(orientation='h', y=1.02, font=dict(size=10)),
        xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=40,b=10))
    for i in range(1, 4):
        fig.update_xaxes(gridcolor='#1e293b', row=i, col=1)
        fig.update_yaxes(gridcolor='#1e293b', row=i, col=1)
    st.plotly_chart(fig, use_container_width=True)

# ── タイトル ──────────────────────────────────────────────────
st.title("📡 kabu3 Pro")
st.caption("マルチTFスキャン ｜ 押し目買いスキャナー ｜ セクターローテーション ｜ 勝率トラッキング")

# ── サイドバー ────────────────────────────────────────────────
# 変数初期化
selected_sectors = []
rsi_ob = 70
rsi_os = 30
bb_std = 2.0
sensitivity = "標準"
trend_filter = True
dmi_filter = False
pb_min = 3.0
pb_max = 15.0
pb_near = 3.0

with st.sidebar:
    st.header("⚙️ スキャン設定")
    sensitivity  = st.radio("シグナル感度", ["標準", "敏感"], horizontal=True)
    trend_filter = st.checkbox("順張りフィルター", value=True)
    dmi_filter   = st.checkbox("DMIフィルター（ADX>20）", value=False)
    st.divider()
    rsi_ob = st.slider("RSI 買われすぎ", 60, 90, 70, 5)
    rsi_os = st.slider("RSI 売られすぎ", 10, 40, 30, 5)
    bb_std = st.slider("ボリンジャーバンド σ", 1.0, 3.0, 2.0, 0.1)
    st.divider()
    st.subheader("📉 押し目買い設定")
    pb_min  = st.slider("押し目 最小(%)", 1.0, 8.0, 3.0, 0.5)
    pb_max  = st.slider("押し目 最大(%)", 8.0, 25.0, 15.0, 1.0)
    pb_near = st.slider("MA接近幅(%)",   1.0, 6.0, 3.0, 0.5)
    st.divider()
    all_sectors      = list(st.session_state['tickers'].keys())
    selected_sectors = st.multiselect("セクター絞り込み（空=全部）", all_sectors)

if selected_sectors:
    target_tickers = {n: c for sec in selected_sectors
                      for n, c in st.session_state['tickers'][sec].items()}
else:
    target_tickers = {n: c for sec in st.session_state['tickers'].values()
                      for n, c in sec.items()}

total_stocks = len(target_tickers)

# ── タブ ─────────────────────────────────────────────────────
tab_oshime, tab_daytrade, tab_scan, tab_result, tab_chart, tab_sector, tab_winrate, tab_manage = st.tabs([
    "📉 押し目(日足)", "⚡ デイトレ", "🔍 スキャン", "📊 結果詳細", "📈 チャート", "🌀 セクター", "🏆 勝率", "➕ 銘柄管理"
])

# ╔══════════════════════════════════════════════════════════╗
# ║   タブ1: 押し目買いスキャナー（メイン機能）                   ║
# ╚══════════════════════════════════════════════════════════╝
with tab_oshime:
    st.subheader("📉 押し目買いスキャナー")
    st.caption("上昇トレンド中に調整してMAに接近した銘柄を自動検出します")

    col1, col2, col3 = st.columns(3)
    col1.metric("対象銘柄", f"{total_stocks}銘柄")
    col2.metric("押し目幅", f"{pb_min}〜{pb_max}%")
    col3.metric("MA接近幅", f"±{pb_near}%")

    if st.button("📉 押し目買いスキャン開始", use_container_width=True, key="oshime_btn"):
        st.session_state.pop('oshime_results', None)
        oshime_results = []
        prog = st.progress(0, text="スキャン中...")
        stbox = st.empty()

        for i, (name, code) in enumerate(target_tickers.items()):
            stbox.info(f"⏳ {name}  [{i+1}/{total_stocks}]")
            r = scan_oshime(code, name, pb_min, pb_max, pb_near)
            if r:
                oshime_results.append(r)
            prog.progress((i+1)/total_stocks, text=f"{i+1}/{total_stocks}")

        prog.progress(1.0, text="✅ 完了！")
        stbox.success(f"✅ 完了！  押し目候補: {len(oshime_results)}銘柄")
        st.session_state['oshime_results'] = oshime_results

        # ── 押し目シグナルのメール送信 ─────────────────────
        best_oshime = [r for r in oshime_results if r.get("スコア",0) >= 7]
        if best_oshime:
            ok, msg = send_buy_alert([], best_oshime)
            if ok:
                st.success(f"📧 押し目シグナルをメール送信！ {msg}")
            else:
                st.warning(f"📧 メール未送信: {msg}")

        # 勝率トラッキングに記録
        if oshime_results:
            df_track = load_tracking()
            today = datetime.now().strftime("%Y-%m-%d")
            new_rows = []
            for r in oshime_results:
                if r["スコア"] >= 6:
                    code = r["コード"]
                    if df_track.empty or not ((df_track["日付"]==today)&(df_track["コード"]==code)).any():
                        new_rows.append({
                            "日付": today, "コード": code, "銘柄名": r["銘柄名"],
                            "種別": "押し目買い", "記録時株価": r["株価"],
                            "3日後":"","5日後":"","3日騰落率":"","勝敗":"追跡中"
                        })
            if new_rows:
                df_new = pd.DataFrame(new_rows)
                df_track = pd.concat([df_track, df_new], ignore_index=True)
                save_tracking(df_track)
                st.info(f"📝 {len(new_rows)}銘柄を勝率トラッキングに記録しました")

    if 'oshime_results' in st.session_state:
        results = st.session_state['oshime_results']
        if not results:
            st.warning("現在、押し目買い候補はありません。条件を緩めてみてください（サイドバーで押し目幅・MA接近幅を広げる）")
        else:
            df_os = pd.DataFrame(results).sort_values("スコア", ascending=False)

            # 絶好の押し目
            best = df_os[df_os["判定"].str.contains("絶好")]
            cand = df_os[df_os["判定"].str.contains("候補")]

            m1, m2 = st.columns(2)
            m1.metric("🟢 絶好の押し目", f"{len(best)}銘柄")
            m2.metric("🟡 押し目候補",   f"{len(cand)}銘柄")
            st.divider()

            # 絶好の押し目カード表示
            if not best.empty:
                st.markdown("### 🟢 絶好の押し目")
                for _, row in best.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{row['銘柄名']}** `{row['コード']}`")
                        c1.write(f"サポート: **{row['サポート']}**　押し目幅: **{row['押し目幅']}**　RSI: {row['RSI']}")
                        c1.caption(f"根拠: {row['根拠']}")
                        c2.metric("株価", f"¥{row['株価']:,}")
                        # エントリー情報
                        e1, e2, e3 = st.columns(3)
                        e1.metric("エントリー",  f"¥{row['エントリー']:,.0f}")
                        e2.metric("損切り",      f"¥{row['損切り']:,.1f}", delta=f"−{((row['エントリー']-row['損切り'])/row['エントリー']*100):.1f}%", delta_color="inverse")
                        e3.metric("利確目標",    f"¥{row['利確目標']:,.0f}", delta=f"+{((row['利確目標']-row['エントリー'])/row['エントリー']*100):.1f}%")
                        # チャートボタン
                        if st.button(f"📊 チャート表示", key=f"oc_{row['コード']}"):
                            st.session_state['oshime_chart'] = row.to_dict()

            st.divider()
            # 候補一覧テーブル
            if not cand.empty:
                st.markdown("### 🟡 押し目候補")
                show_cols = ["銘柄名","コード","株価","直近高値","押し目幅","サポート","RSI","出来高比","MACDボトム","スコア","エントリー","損切り","利確目標"]
                st.dataframe(cand[show_cols].reset_index(drop=True), use_container_width=True, hide_index=True)

            # チャート表示（ボタン押した場合）
            if 'oshime_chart' in st.session_state:
                r = st.session_state['oshime_chart']
                st.divider()
                st.markdown(f"#### 📈 {r['銘柄名']} チャート")
                draw_chart(r['コード'], r['銘柄名'],
                           entry=r['エントリー'], stop=r['損切り'], target=r['利確目標'])

# ═══════════════ タブ2: デイトレ押し目 ════════════════════════════
with tab_daytrade:
    st.subheader("⚡ デイトレ押し目スキャナー")
    st.caption("1時間足・5分足でRSI売られすぎ＋BB下限タッチを検出")

    col1, col2 = st.columns(2)
    col1.metric("対象銘柄", f"{total_stocks}銘柄")
    col2.metric("時間軸", "1時間足 ＋ 5分足")

    if st.button("⚡ デイトレスキャン開始", use_container_width=True, key="daytrade_btn"):
        st.session_state.pop('daytrade_results', None)
        results_1h = []
        results_5m = []
        prog = st.progress(0, text="スキャン中...")
        stbox = st.empty()

        for i, (name, code) in enumerate(target_tickers.items()):
            stbox.info(f"⏳ {name}  [{i+1}/{total_stocks}]")
            r1h = scan_oshime_1h(code, name)
            r5m = scan_oshime_5m(code, name)
            if r1h: results_1h.append(r1h)
            if r5m: results_5m.append(r5m)
            prog.progress((i+1)/total_stocks, text=f"{i+1}/{total_stocks}")

        prog.progress(1.0, text="✅ 完了！")
        stbox.success(f"✅ 完了！  1h:{len(results_1h)}銘柄 / 5分:{len(results_5m)}銘柄")
        st.session_state['daytrade_results'] = {
            "1h": results_1h, "5m": results_5m
        }

        # メール送信
        all_dt = results_1h + results_5m
        best_dt = [r for r in all_dt if r.get("スコア", 0) >= 7]
        if best_dt:
            ok, msg = send_buy_alert([], best_dt)
            if ok:
                st.success(f"📧 デイトレシグナルをメール送信！ {msg}")

    if 'daytrade_results' in st.session_state:
        dt = st.session_state['daytrade_results']
        results_1h = dt.get("1h", [])
        results_5m = dt.get("5m", [])

        # 両TF一致（最強）
        codes_1h = {r["コード"] for r in results_1h}
        codes_5m = {r["コード"] for r in results_5m}
        both     = codes_1h & codes_5m

        if both:
            st.markdown("### 🔥 1時間足＋5分足 両方シグナル（最強）")
            for code in both:
                r = next(r for r in results_1h if r["コード"] == code)
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{r['銘柄名']}** `{r['コード']}`　🔥 両TF一致")
                    c1.write(f"RSI(1h):{r['RSI']}  BB下限:{r['BB下限']}  {r['根拠']}")
                    c2.metric("株価", f"¥{r['株価']:,}")
                    e1, e2, e3 = st.columns(3)
                    e1.metric("エントリー", f"¥{r['エントリー']:,}")
                    e2.metric("損切り",     f"¥{r['損切り']:,}")
                    e3.metric("利確(+3%)",  f"¥{r['利確目標']:,}")
            st.divider()

        sub_1h, sub_5m = st.tabs(["⏱ 1時間足", "⚡ 5分足"])

        with sub_1h:
            st.markdown(f"### ⏱ 1時間足 押し目候補　{len(results_1h)}銘柄")
            if not results_1h:
                st.info("現在なし")
            else:
                df_1h = pd.DataFrame(results_1h).sort_values("スコア", ascending=False)
                show = ["銘柄名","コード","株価","RSI","RSI最小","BB下限","サポート","MACDボトム","スコア","判定","エントリー","損切り","利確目標"]
                show = [c for c in show if c in df_1h.columns]
                df_1h_show = df_1h[show].reset_index(drop=True)
                event_1h = st.dataframe(df_1h_show, use_container_width=True, hide_index=True,
                                        on_select="rerun", selection_mode="single-row")
                if event_1h.selection.rows:
                    sel = df_1h_show.iloc[event_1h.selection.rows[0]]
                    st.markdown(f"#### 📈 {sel['銘柄名']} チャート（1時間足）")
                    draw_chart(sel['コード'], sel['銘柄名'])

        with sub_5m:
            st.markdown(f"### ⚡ 5分足 押し目候補　{len(results_5m)}銘柄")
            if not results_5m:
                st.info("現在なし")
            else:
                df_5m = pd.DataFrame(results_5m).sort_values("スコア", ascending=False)
                show = ["銘柄名","コード","株価","RSI","RSI最小","BB下限","サポート","MACDボトム","スコア","判定","エントリー","損切り","利確目標"]
                show = [c for c in show if c in df_5m.columns]
                df_5m_show = df_5m[show].reset_index(drop=True)
                event_5m = st.dataframe(df_5m_show, use_container_width=True, hide_index=True,
                                        on_select="rerun", selection_mode="single-row")
                if event_5m.selection.rows:
                    sel = df_5m_show.iloc[event_5m.selection.rows[0]]
                    st.markdown(f"#### 📈 {sel['銘柄名']} チャート（5分足）")
                    draw_chart(sel['コード'], sel['銘柄名'])

# ═══════════════ タブ2: スキャン ════════════════════════════════
with tab_scan:
    c1, c2 = st.columns(2)
    c1.metric("対象銘柄数", f"{total_stocks}銘柄")
    c2.metric("スキャンTF数", "3（日足・1h・5分）")

    if st.button("🔍 マルチTFスキャン開始", use_container_width=True, key="scan_btn"):
        st.session_state.pop('scan_results', None)
        results = []
        sector_stats = {}
        prog = st.progress(0, text="スキャン準備中...")
        stbox = st.empty()
        code_to_sector = {c: sec for sec, d in st.session_state['tickers'].items() for n, c in d.items()}

        for i, (name, code) in enumerate(target_tickers.items()):
            stbox.info(f"⏳ {name}  [{i+1}/{total_stocks}]")
            row = {"銘柄名": name, "コード": code, "セクター": code_to_sector.get(code,"その他")}
            for tf_label, cfg in TF_CONFIG.items():
                sig, rsi_v, stoch_v, adx_v, ma25_b, sig_time = scan_one(
                    code, cfg["tf"], cfg["period"], rsi_ob, rsi_os, sensitivity, trend_filter, dmi_filter, bb_std)
                row[tf_label]              = sig
                row[f"RSI({tf_label})"]   = rsi_v
                row[f"Stoch({tf_label})"] = stoch_v
                row[f"ADX({tf_label})"]   = adx_v
                # シグナル発生時刻（1h・5分のみ）
                if tf_label in ["1時間足", "5分足"] and sig == "🟢":
                    row[f"時刻({tf_label})"] = sig_time or ""
                elif tf_label not in [f"時刻({t})" for t in ["1時間足","5分足"]]:
                    if f"時刻({tf_label})" not in row:
                        row[f"時刻({tf_label})"] = ""
                if tf_label == "日足":
                    row["MA25反発"] = "★" if ma25_b else ""
            buy_count  = sum(1 for tfl in TF_CONFIG if row[tfl] == "🟢")
            row["一致数"] = buy_count
            row["強度"]   = "★★★" if buy_count==3 else "★★☆" if buy_count==2 else "★☆☆" if buy_count==1 else "－"
            results.append(row)
            sec = row["セクター"]
            if sec not in sector_stats:
                sector_stats[sec] = {"total":0,"buy":0,"sell":0,"star3":0}
            sector_stats[sec]["total"] += 1
            if buy_count >= 1: sector_stats[sec]["buy"] += 1
            if buy_count == 3: sector_stats[sec]["star3"] += 1
            if any(row[tfl]=="🔴" for tfl in TF_CONFIG): sector_stats[sec]["sell"] += 1
            prog.progress((i+1)/total_stocks, text=f"{i+1}/{total_stocks}")

        prog.progress(1.0, text="✅ 完了！")
        stbox.success(f"✅ {total_stocks}銘柄スキャン完了！")
        st.session_state['scan_results'] = results
        st.session_state['sector_stats'] = sector_stats

        # ── メール送信 ──────────────────────────────────────
        star2up = [r for r in results if r.get("一致数",0) >= 2]
        ma25buy = [r for r in results if r.get("MA25反発","") == "★" and r.get("一致数",0) >= 1]
        send_targets = {r["コード"]: r for r in star2up + ma25buy}.values()
        if send_targets:
            ok, msg = send_buy_alert(list(send_targets), [])
            if ok:
                st.success(f"📧 メール送信完了！ {msg}")
            else:
                st.warning(f"📧 メール未送信: {msg}")

    if 'scan_results' in st.session_state:
        df_all = pd.DataFrame(st.session_state['scan_results'])
        buy_df = df_all[df_all['一致数']>0]
        str3 = buy_df[buy_df['一致数']==3]
        str2 = buy_df[buy_df['一致数']==2]
        str1 = buy_df[buy_df['一致数']==1]
        st.divider()
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("★★★",f"{len(str3)}銘柄")
        m2.metric("★★☆",f"{len(str2)}銘柄")
        m3.metric("★☆☆",f"{len(str1)}銘柄")
        m4.metric("25日線反発",f"{len(df_all[df_all['MA25反発']=='★'])}銘柄")
        st.info("👉「結果詳細」タブで詳しく確認できます")

# ═══════════════ タブ3: 結果詳細 ════════════════════════════════
with tab_result:
    if 'scan_results' not in st.session_state:
        st.info("先に「スキャン」タブを実行してください。")
    else:
        df_all = pd.DataFrame(st.session_state['scan_results'])
        buy_df = df_all[df_all['一致数']>0].sort_values('一致数', ascending=False)

        def signal_cards(tf_col, tf_key):
            buy_rows  = df_all[df_all[tf_col]=="🟢"].sort_values('一致数', ascending=False)
            sell_rows = df_all[df_all[tf_col]=="🔴"].sort_values('一致数', ascending=False)
            wait_rows = df_all[df_all[tf_col]=="➖"]
            ca,cb,cc = st.columns(3)
            ca.metric("🟢 買い",f"{len(buy_rows)}銘柄")
            cb.metric("🔴 売り",f"{len(sell_rows)}銘柄")
            cc.metric("➖ 様子見",f"{len(wait_rows)}銘柄")
            st.divider()
            # 🟢 買い銘柄 表形式（クリックでチャート）
            if not buy_rows.empty:
                st.markdown("### 🟢 買い銘柄　　*← 行をクリックするとチャートが表示されます*")
                show_cols = ["銘柄名","コード","セクター","日足","1時間足","時刻(1時間足)","5分足","時刻(5分足)","強度","MA25反発",
                             f"RSI({tf_key})",f"Stoch({tf_key})",f"ADX({tf_key})"]
                show_cols = [c for c in show_cols if c in buy_rows.columns]
                df_show = buy_rows[show_cols].reset_index(drop=True)
                event = st.dataframe(df_show, use_container_width=True, hide_index=True,
                                     on_select="rerun", selection_mode="single-row")
                if event.selection.rows:
                    sel = df_show.iloc[event.selection.rows[0]]
                    st.markdown(f"#### 📈 {sel['銘柄名']} チャート")
                    draw_chart(sel['コード'], sel['銘柄名'])
            else:
                st.info("🟢 買いシグナルなし")
            st.divider()
            # 🔴 売り銘柄 表形式（クリックでチャート）
            if not sell_rows.empty:
                st.markdown("### 🔴 売り銘柄　　*← 行をクリックするとチャートが表示されます*")
                show_cols = ["銘柄名","コード","セクター","日足","1時間足","5分足",
                             f"RSI({tf_key})",f"Stoch({tf_key})"]
                show_cols = [c for c in show_cols if c in sell_rows.columns]
                df_show_s = sell_rows[show_cols].reset_index(drop=True)
                event_s = st.dataframe(df_show_s, use_container_width=True, hide_index=True,
                                       on_select="rerun", selection_mode="single-row")
                if event_s.selection.rows:
                    sel = df_show_s.iloc[event_s.selection.rows[0]]
                    st.markdown(f"#### 📈 {sel['銘柄名']} チャート")
                    draw_chart(sel['コード'], sel['銘柄名'])
            if not wait_rows.empty:
                with st.expander(f"➖ 様子見 {len(wait_rows)}銘柄"):
                    st.write("　".join(wait_rows['銘柄名'].tolist()))

        # ── 25日線反発 表形式表示（一番上）────────────────────
        ma25_rows = df_all[df_all["MA25反発"] == "★"].sort_values("一致数", ascending=False)
        st.markdown("### ★ 25日線反発銘柄")
        if not ma25_rows.empty:
            show_ma25 = ["銘柄名","コード","セクター","日足","1時間足","時刻(1時間足)","5分足","時刻(5分足)","強度","RSI(日足)","Stoch(日足)","ADX(日足)"]
            show_ma25 = [c for c in show_ma25 if c in ma25_rows.columns]
            df_ma25_show = ma25_rows[show_ma25].reset_index(drop=True)
            event_ma25 = st.dataframe(df_ma25_show, use_container_width=True, hide_index=True,
                                      on_select="rerun", selection_mode="single-row")
            if event_ma25.selection.rows:
                sel = df_ma25_show.iloc[event_ma25.selection.rows[0]]
                st.markdown(f"#### 📈 {sel['銘柄名']} チャート")
                draw_chart(sel['コード'], sel['銘柄名'])
        else:
            st.info("現在、25日線反発銘柄はありません。スキャンを実行してください。")
        st.divider()

        sub_all,sub_1d,sub_1h,sub_5m,sub_strong = st.tabs(["🗒 全銘柄","📅 日足","⏱ 1時間足","⚡ 5分足","🏆 複数TF一致"])
        SHOW = ["銘柄名","コード","セクター","日足","1時間足","時刻(1時間足)","5分足","時刻(5分足)","強度","MA25反発"]
        with sub_all:
            st.dataframe(df_all.sort_values('一致数',ascending=False)[SHOW].reset_index(drop=True), use_container_width=True, hide_index=True)
        with sub_1d: signal_cards("日足","日足")
        with sub_1h: signal_cards("1時間足","1時間足")
        with sub_5m: signal_cards("5分足","5分足")
        with sub_strong:
            st.subheader("🏆 3TF全一致")
            str3 = buy_df[buy_df['一致数']==3]
            if str3.empty: st.info("現在なし")
            else:
                for _,row in str3.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['銘柄名']}** `{row['コード']}`　{row.get('MA25反発','')}")
                        st.write(f"日足 {row['日足']}　1h {row['1時間足']}　5分 {row['5分足']}")

# ═══════════════ タブ4: チャート ════════════════════════════════
with tab_chart:
    st.subheader("📈 チャート")
    all_names = {n: c for sec in st.session_state['tickers'].values() for n, c in sec.items()}
    sel_name = st.selectbox("銘柄を選択", list(all_names.keys()), key="chart_select")
    sel_code = all_names[sel_name]
    if st.button("📊 チャート表示", use_container_width=True):
        with st.spinner("取得中..."):
            draw_chart(sel_code, sel_name)

# ═══════════════ タブ5: セクター ════════════════════════════════
with tab_sector:
    st.subheader("🌀 セクターローテーション分析")
    if 'sector_stats' not in st.session_state:
        st.info("先にスキャンを実行してください。")
    else:
        stats = st.session_state['sector_stats']
        rows  = [{"セクター":sec,"買い銘柄":d["buy"],"★★★":d["star3"],"売り銘柄":d["sell"],"対象":d["total"],
                  "注目度":"🔥 熱い" if d["buy"]>=4 else "🟠 注目" if d["buy"]>=2 else "🟡 やや" if d["buy"]>=1 else "－"}
                 for sec,d in stats.items()]
        df_sec = pd.DataFrame(rows).sort_values("買い銘柄", ascending=False).reset_index(drop=True)
        st.dataframe(df_sec, use_container_width=True, hide_index=True)
        top3 = df_sec.head(3)
        st.divider()
        st.markdown("#### 💰 今日注目のセクター TOP3")
        cols = st.columns(3)
        for i,(_,row) in enumerate(top3.iterrows()):
            cols[i].metric(row["セクター"],f"買い {row['買い銘柄']}銘柄",row["注目度"])

# ═══════════════ タブ6: 勝率 ════════════════════════════════════
with tab_winrate:
    st.subheader("🏆 勝率トラッキング")
    col1, col2 = st.columns(2)
    if col1.button("📊 勝率データを更新", use_container_width=True):
        with st.spinner("更新中..."):
            df_track = update_tracking()
            st.success("✅ 更新完了！")
    if col2.button("🗑 全データリセット", use_container_width=True):
        if os.path.exists(TRACKING_FILE): os.remove(TRACKING_FILE)
        st.success("リセットしました。")
    df_track = load_tracking()
    if df_track.empty:
        st.info("まだ記録がありません。スキャンを実行すると自動記録されます。")
    else:
        decided  = df_track[df_track["勝敗"].isin(["✅ 勝","❌ 負"])]
        wins     = len(decided[decided["勝敗"]=="✅ 勝"])
        win_rate = round(wins/len(decided)*100,1) if len(decided) else 0
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("総記録数",f"{len(df_track)}件")
        m2.metric("✅ 勝ち",f"{wins}件")
        m3.metric("❌ 負け",f"{len(decided)-wins}件")
        m4.metric("勝率",f"{win_rate}%")
        st.dataframe(df_track.sort_values("日付",ascending=False).reset_index(drop=True),
                     use_container_width=True, hide_index=True)

# ═══════════════ タブ7: 銘柄管理 ════════════════════════════════
with tab_manage:
    st.subheader("➕ 銘柄を追加する")
    with st.form("add_ticker_form", clear_on_submit=True):
        col_a,col_b,col_c = st.columns([2,2,2])
        new_name   = col_a.text_input("銘柄名", placeholder="例: 信越化学")
        new_code   = col_b.text_input("銘柄コード", placeholder="例: 4063.T")
        new_sector = col_c.text_input("セクター", placeholder="例: 化学・素材")
        if st.form_submit_button("✅ 追加する", use_container_width=True):
            if new_name and new_code:
                sector = new_sector.strip() if new_sector.strip() else "その他"
                if sector not in st.session_state['tickers']:
                    st.session_state['tickers'][sector] = {}
                st.session_state['tickers'][sector][new_name.strip()] = new_code.strip().upper()
                save_tickers()
                st.success(f"✅ 「{new_name}」を追加しました！")
                st.rerun()
            else:
                st.error("銘柄名とコードは必須です。")
    st.divider()
    for sector, ticker_dict in list(st.session_state['tickers'].items()):
        with st.expander(f"📂 {sector}（{len(ticker_dict)}銘柄）"):
            for t_name, t_code in list(ticker_dict.items()):
                c1,c2,c3 = st.columns([3,2,1])
                c1.write(t_name); c2.code(t_code)
                if c3.button("🗑", key=f"del_{sector}_{t_name}"):
                    del st.session_state['tickers'][sector][t_name]
                    if not st.session_state['tickers'][sector]: del st.session_state['tickers'][sector]
                    save_tickers(); st.rerun()
    st.divider()
    if st.button("🔄 デフォルトに戻す", use_container_width=True):
        st.session_state['tickers'] = DEFAULT_TICKERS
        save_tickers(); st.success("デフォルトに戻しました。"); st.rerun()
