import requests
import pandas as pd
import numpy as np
import os
import time

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# STRATEJİ AYARLARI
FUNDING_LIMIT = 0.02
RSI_LIMIT = 70
CHANGE_24H_LIMIT = 8
WHALE_WALL_RATIO = 2.5

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

# MANUEL RSI HESAPLAMA
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_market_trend():
    btc = get_data("/api/v5/market/tickers", {"instId": "BTC-USDT-SWAP"})
    if btc:
        change = (float(btc[0]['last']) / float(btc[0]['open24h']) - 1) * 100
        return f"%{round(change, 2)} {'📉' if change < 0 else '📈'}"
    return "BELİRSİZ"

def check_whale_walls(symbol):
    depth = get_data("/api/v5/market/books", {"instId": symbol, "sz": "20"})
    if not depth: return 1, 0
    asks = sum([float(a[1]) for a in depth[0]['asks']])
    bids = sum([float(b[1]) for b in depth[0]['bids']])
    return (asks / bids if bids > 0 else 1), asks

def scan():
    trend = get_market_trend()
    tickers = get_data("/api/v5/market/tickers", {"instType": "SWAP"})
    
    # --- DEĞİŞEN TEK SATIR BURASI: [:100] SİLİNDİ, TÜM PARİTELERİ TARAR ---
    tickers = sorted(tickers, key=lambda x: float(x['vol24h']), reverse=True)
    # ---------------------------------------------------------------------
    
    signals = []
    for t in tickers:
        symbol = t['instId']
        if "-USDT-" not in symbol: continue
        
        change = (float(t['last']) / float(t['open24h']) - 1) * 100
        if change > CHANGE_24H_LIMIT:
            # 1. Teknik Veri (RSI)
            candles = get_data("/api/v5/market/candles", {"instId": symbol, "bar": "1H", "limit": "50"})
            if not candles: continue
            df = pd.DataFrame(candles, columns=['ts','o','h','l','c','v','vc','vq','conf'])
            df['c'] = df['c'].astype(float)
            
            # Kendi RSI fonksiyonumuzu kullanıyoruz
            rsi_series = calculate_rsi(df['c'][::-1]) 
            rsi = rsi_series.iloc[-1]
            
            # 2. Fonlama ve Balina Verisi
            funding = get_data("/api/v5/public/funding-rate", {"instId": symbol})
            f_rate = float(funding[0]['fundingRate']) * 100 if funding else 0
            wall_ratio, ask_vol = check_whale_walls(symbol)
            
            # SİNYAL KOŞULLARI
            if rsi > RSI_LIMIT or wall_ratio > WHALE_WALL_RATIO:
                msg = (f"🚨 *SHORT SİNYALİ: {symbol}*\n\n"
                       f"🌍 BTC 24s: {trend}\n"
                       f"📈 24s Değişim: %{round(change, 2)}\n"
                       f"📊 RSI (1H): {round(rsi, 2)}\n"
                       f"💸 Funding: %{round(f_rate, 4)}\n"
                       f"🧱 Balina Duvarı: {round(wall_ratio, 1)}x\n")
                signals.append(msg)
                
    if signals:
        send_telegram("\n---\n".join(signals))

if __name__ == "__main__":
    scan()
