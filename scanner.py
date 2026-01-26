import requests
import pandas as pd
import pandas_ta as ta
import os
import time

# GitHub Secrets
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# STRATEJİ AYARLARI
FUNDING_LIMIT = 0.02  # %0.02 ve üzeri
RSI_LIMIT = 70
CHANGE_24H_LIMIT = 8
WHALE_WALL_RATIO = 2.5 # Satış emirleri, alış emirlerinden 2.5 kat fazlaysa "duvar" var demektir.

def send_telegram(msg):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def get_data(endpoint, params={}):
    base = "https://www.okx.com"
    try:
        res = requests.get(base + endpoint, params=params).json()
        return res.get('data', [])
    except: return []

def check_whale_walls(symbol):
    # Order Book (Derinlik) verisini al
    depth = get_data("/api/v5/market/books", {"instId": symbol, "sz": "20"})
    if not depth: return 1, "Bilinmiyor"
    
    asks = depth[0]['asks'] # Satış emirleri
    bids = depth[0]['bids'] # Alış emirleri
    
    total_ask_vol = sum([float(a[1]) for a in asks])
    total_bid_vol = sum([float(b[1]) for b in bids])
    
    ratio = total_ask_vol / total_bid_vol if total_bid_vol > 0 else 1
    return ratio, total_ask_vol

def scan():
    tickers = get_data("/api/v5/market/tickers", {"instType": "SWAP"})
    tickers = sorted(tickers, key=lambda x: float(x['vol24h']), reverse=True)[:100]
    
    signals = []
    
    for t in tickers:
        symbol = t['instId']
        change = (float(t['last']) / float(t['open24h']) - 1) * 100
        
        if change > CHANGE_24H_LIMIT:
            # 1. Teknik ve Fonlama Verileri
            funding = get_data("/api/v5/public/funding-rate", {"instId": symbol})
            f_rate = float(funding[0]['fundingRate']) * 100 if funding else 0
            
            candles = get_data("/api/v5/market/candles", {"instId": symbol, "bar": "1H", "limit": "50"})
            if not candles: continue
            df = pd.DataFrame(candles, columns=['ts','o','h','l','c','v','vc','vq','conf'])
            df['c'] = df['c'].astype(float)
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            
            # 2. Balina Duvarı Kontrolü
            wall_ratio, ask_vol = check_whale_walls(symbol)
            
            # KRİTER: RSI yüksekse VEYA (Fiyat artmış + Fonlama yüksek + Balina duvarı var)
            if (rsi > RSI_LIMIT and wall_ratio > WHALE_WALL_RATIO) or f_rate > 0.05:
                status = "🚨 KRİTİK SHORT" if wall_ratio > 4 else "⚠️ SHORT ADAYI"
                
                msg = (f"{status}: *{symbol}*\n\n"
                       f"📈 24s Değişim: %{round(change, 2)}\n"
                       f"📊 RSI (1H): {round(rsi, 2)}\n"
                       f"💸 Funding: %{round(f_rate, 4)}\n"
                       f"🧱 Balina Duvarı: {round(wall_ratio, 1)}x (Satış Baskısı)\n"
                       f"🔍 Üstteki Satış Hacmi: {int(ask_vol)} Adet")
                signals.append(msg)
                
    if signals:
        send_telegram("\n---\n".join(signals))

if __name__ == "__main__":
    scan()
