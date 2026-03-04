import sys
import subprocess
import time
import logging
import warnings
import asyncio
import random
import json
import os
from datetime import datetime, timedelta, time as dt_time, timezone
import pytz 
import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
from scipy.stats import zscore

# --- 库引用隔离 (IBKR 专用) ---
from ib_insync import *
import nest_asyncio 
# ------------------

# 屏蔽噪音
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

nest_asyncio.apply()

# ================= 🔑 IBKR 连接配置 =================
IB_HOST = '127.0.0.1'
IB_PORT = 7497       # 7497 = 模拟盘, 7496 = 实盘
IB_CLIENT_ID = random.randint(100, 9999) 

# ================= 🏆 极简王道风控参数 (V29.87 滤震版) =================
RISK_FACTOR = 0.02           
CASH_RESERVE = 0.20          

PARAMS = {
    'MIN_ORDER_USD': 500.0,      
    'MIN_SCORE_TO_BUY': 55,      
    'ATR_STOP_MULT': 2.8,        
    'PROFIT_TARGET_ATR_MULT': 3.0,
    'NORMAL_ACTIVATION': 0.03,
    'MORNING_ACTIVATION': 0.01,
    'FLIP_SCORE_THRESHOLD': 60,
    'RVOL_FLIP_THRESHOLD': 1.5,
    'SWAP_THRESHOLD': 70,         
    'INTRA_SWAP_THRESHOLD': 65,   
    'COMMONER_CAP_PCT': 0.20,     
    'HEDGE_CAP_PCT': 0.30,        
    'SECTOR_HARD_CAP_PCT': 0.40,  
    'BREAKEVEN_TRIGGER_PCT': 0.015, 
    'TIME_STOP_SECONDS': 2700,    
    'NEWBORN_IMMUNITY_SEC': 300,     
    'SWAP_FRICTION_PENALTY': 15,     
    'TRENCH_DEFENSE_SEC': 180,       
    
    # 🚨 V29.88 智能动态追踪锁 (基于本金比例与大盘趋势)
    'DAILY_TARGET_PCT': 0.01,         # 1% 本金作为初始目标
    'TRAILING_TOLERANCE_NORMAL': 0.25,# 正常大盘下，容忍25%利润回撤
    'TRAILING_TOLERANCE_BULL': 0.35,  # 大盘强势单边上涨时，放宽到容忍35%回撤，让利润奔跑
    'TRAILING_TOLERANCE_BEAR': 0.15,  # 大盘走弱破位时，收紧到15%回撤，落袋为安
}

LEVERAGED_ETFS = {
    "SOXL", "SOXS", "TQQQ", "SQQQ", "TECL", "TECS", 
    "LABU", "LABD", "FNGU", "FNGD", "NVDL", "USD", 
    "TSLT", "TSLZ", "SPXU"
}

COMMODITY_ASSETS = {
    "GLD", "IAU", "GLL", "UGL", "NEM", "FCX", "XOM", "CVX"
}

NOBLES_SET = {
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MSFT", "GOOGL", "META", "AMZN", "PLTR",
    "SOXL", "USD", "NVDL", "TQQQ", "TECL", "FNGU", "BULZ",
    "MSTR", "COIN", "IBIT", 
    "LLY", "NVO",   
    "VST", "CEG", "NRG", "GEV", 
    "CAT", "WMT", "COST", "XOM" 
}

COMMONERS_SET = {
    "CVX", "JPM", "V", "MA", "BRK.B",
    "NEM", "FCX", "GLD", "UGL", "IAU",
    "GE", "RTX", "LMT", "WM",
    "AAPL", "NFLX", "ADBE", "MU", "INTC", "QCOM" 
}

LONG_TARGETS = {
    "NVDA": "XLK", "AMD": "XLK", "AVGO": "XLK", "TSM": "XLK",
    "ARM": "XLK", "MU": "XLK", "INTC": "XLK", "QCOM": "XLK",
    "SOXL": "XLK", "USD": "XLK", "NVDL": "XLK", 
    "AAPL": "XLK", "MSFT": "XLK", "GOOGL": "XLC", "META": "XLC", 
    "AMZN": "XLY", "NFLX": "XLC", "ADBE": "XLK", "PLTR": "XLK", 
    "TQQQ": "XLK", "TECL": "XLK", "FNGU": "XLK", "BULZ": "XLK",
    "MSTR": "IBIT", "COIN": "IBIT", 
    "LLY": "XLV", "NVO": "XLV",
    "VST": "XLU", "CEG": "XLU", "NRG": "XLU", "GEV": "XLI",
    "JPM": "XLF", "V": "XLF", "BRK.B": "XLF",
    "CVX": "XLE", "XOM": "XLE", 
    "NEM": "XLB", "FCX": "XLB", "GLD": "GLD", "UGL": "GLD", "IAU": "GLD",
    "GE": "XLI", "RTX": "XLI", "LMT": "XLI", "WM": "XLI", "CAT": "XLI",
    "COST": "XLP", "WMT": "XLP"
}

HEDGE_TARGETS = {
    "SQQQ": "XLK", "SOXS": "XLK", "LABD": "XLV", 
    "FNGD": "XLK", "SPXU": "SPY",
    "GLL": "GLD", "TECS": "XLK", 
    "TSLZ": "XLY", "NVD": "XLK"
}

TARGET_MAP = {**LONG_TARGETS, **HEDGE_TARGETS}

CONFLICT_PAIRS = {
    "SOXL": "SOXS", "SOXS": "SOXL", 
    "TQQQ": "SQQQ", "SQQQ": "TQQQ",
    "TECL": "TECS", "TECS": "TECL", 
    "LABU": "LABD", "LABD": "LABU", 
    "FNGU": "FNGD", "FNGD": "FNGU",
    "TSLT": "TSLZ", "TSLZ": "TSLT",
    "NVDL": "NVD",  "NVD": "NVDL",
    "GLD": "GLL",   "GLL": "GLD",
    "UGL": "GLL",   "IAU": "GLL",
    "NVDA": "NVD",  "NVD": "NVDA",
    "TSLA": "TSLZ", "TSLZ": "TSLA",
    "AAPL": "TECS", "MSFT": "TECS",
    "AVGO": "SOXS", "AMD": "SOXS", "TSM": "SOXS",
    "NVDA": "SOXS", "ARM": "SOXS",
    "LLY": "LABD", "NVO": "LABD"
}

CORRELATED_GROUPS = [
    {"SQQQ", "SOXS", "FNGD", "TECS"}, 
    {"TQQQ", "SOXL", "FNGU", "TECL", "NVDL", "USD", "NVDA", "AMD", "AVGO", "TSM", "ARM", "MU", "INTC", "QCOM"}, 
    {"AAPL", "MSFT", "GOOGL", "META", "AMZN", "NFLX", "ADBE", "PLTR"}, 
    {"CVX", "XOM"}, 
    {"VST", "CEG", "NRG", "GEV"}, 
    {"MSTR", "COIN", "IBIT"}, 
    {"LLY", "NVO"}, 
    {"GE", "RTX", "LMT"} 
]

ETF_COMPONENTS = {
    "SOXL": ["NVDA", "AMD", "AVGO", "TSM", "QCOM"], 
    "SOXS": ["NVDA", "AMD", "AVGO", "TSM", "QCOM"], 
    "TQQQ": ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL"], 
    "SQQQ": ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL"], 
    "TECL": ["AAPL", "MSFT", "NVDA"], 
    "FNGU": ["NVDA", "META", "NFLX", "GOOGL"], 
    "TSLT": ["TSLA"], 
    "TSLZ": ["TSLA"],
    "NVDL": ["NVDA"], 
    "NVD":  ["NVDA"]
}

BETA_MAP = {
    "SOXL": 3.0, "TQQQ": 3.0, "TECL": 3.0, "FNGU": 3.0, "LABU": 3.0, "USD": 2.0, "NVDL": 2.0, "TSLT": 2.0,
    "SOXS": -3.0, "SQQQ": -3.0, "TECS": -3.0, "FNGD": -3.0, "LABD": -3.0, "SPXU": -3.0, "TSLZ": -2.0, "NVD": -2.0,
    "NVDA": 1.8, "AMD": 1.8, "AVGO": 1.5, "TSM": 1.3, "ARM": 1.8, "MU": 1.6, "INTC": 1.2, "QCOM": 1.3,
    "AAPL": 1.1, "MSFT": 1.1, "GOOGL": 1.1, "META": 1.3, "AMZN": 1.2, "NFLX": 1.2, "ADBE": 1.2, "PLTR": 2.0,
    "MSTR": 3.0, "COIN": 2.5, "IBIT": 1.5,
    "CVX": 0.7, "XOM": 0.7, "CEG": 1.1, "VST": 1.2, "NRG": 1.0, "GEV": 1.1,
    "JPM": 1.0, "V": 1.0, "MA": 1.0, "BRK.B": 0.8,
    "NEM": 0.4, "FCX": 1.2, "GLD": 0.1, "IAU": 0.1, "UGL": 0.2, "GLL": -0.2,
    "GE": 1.1, "RTX": 0.7, "LMT": 0.6, "WM": 0.8, "CAT": 1.0, "COST": 0.7, "WMT": 0.6,
    "LLY": 0.7, "NVO": 0.6
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger()
ib = IB()

def connect_ib():
    try:
        if ib.isConnected(): return True
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
        return True
    except Exception as e:
        logger.error(f"🛑 连接异常: {e}")
        return False

def get_market_status_and_regime():
    try:
        nyc = pytz.timezone('US/Eastern')
        now = datetime.now(nyc)
        if now.weekday() >= 5: return 0, "🌴 周末休市", False, "CLOSED"
        
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        if now < market_open: return 999, f"☕ 盘前等待", False, "PRE"
        if now >= market_close: return 0, "🌙 已收盘", False, "CLOSED"
        
        delta = market_close - now
        minutes_left = delta.total_seconds() / 60.0
        
        current_time_val = now.time()
        
        if current_time_val < dt_time(9, 45):
            regime = "ORB_COOLOFF"
            tag_msg = "🌅 盲区 (只看不买)"
        elif current_time_val < dt_time(10, 30):
            regime = "MORNING"
            tag_msg = "🌅 早盘突破与收割"
        elif current_time_val < dt_time(14, 0):
            regime = "MIDDAY"
            tag_msg = "🍱 午盘猎手"
        elif current_time_val < dt_time(15, 55):
            regime = "AFTERNOON"
            tag_msg = "⚡ 尾盘机构趋势"
        else:
            regime = "POWER_CLOSE"
            tag_msg = "🛑 尾盘禁区"
            
        return minutes_left, tag_msg, True, regime
    except: return 300, "⚠️ 时间获取失败", True, "MIDDAY"

def get_data_realtime_ibkr(symbol):
    try:
        yf_symbol = symbol.replace(".", "-") if "BRK" in symbol else symbol
        df_daily_hist = yf.download(yf_symbol, period="3mo", interval="1d", progress=False, auto_adjust=False)
        daily_sma_val = 0.0
        if not df_daily_hist.empty and len(df_daily_hist) >= 20:
            if isinstance(df_daily_hist.columns, pd.MultiIndex): df_daily_hist.columns = df_daily_hist.columns.get_level_values(0)
            df_daily_hist['SMA_20'] = ta.sma(df_daily_hist['Close'], 20)
            daily_sma_val = df_daily_hist['SMA_20'].iloc[-1]

        ib_symbol = symbol.replace(".", " ") if "BRK" in symbol else symbol
        contract = Stock(ib_symbol, 'SMART', 'USD')
        bars = ib.reqHistoricalData(contract, endDateTime='', durationStr='5 D', barSizeSetting='5 mins', whatToShow='TRADES', useRTH=True, formatDate=1, keepUpToDate=False)
        if not bars: return pd.DataFrame()
        df = util.df(bars)
        if df is None or df.empty: return pd.DataFrame()
        df.rename(columns={'date': 'Datetime', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
        df.set_index('Datetime', inplace=True)
        if df.index.tz is None: df.index = df.index.tz_localize('US/Eastern')
        else: df.index = df.index.tz_convert('US/Eastern')
        
        df['SMA_200'] = ta.sma(df['Close'], 200); df['SMA_20'] = ta.sma(df['Close'], 20); df['EMA_20'] = ta.ema(df['Close'], 20); df['Vol_SMA'] = ta.sma(df['Volume'], 20)
        df['EMA_9'] = ta.ema(df['Close'], 9) 
        df['Daily_SMA_20'] = daily_sma_val; df['Daily_Trend_Ok'] = True 
        try: df['HMA_55'] = ta.hma(df['Close'], 55); df['HMA_21'] = ta.hma(df['Close'], 21)
        except: pass 
        if 'HMA_55' not in df.columns: df['HMA_55'] = df['SMA_20']
        if 'HMA_21' not in df.columns: df['HMA_21'] = df['SMA_20']
        bb = ta.bbands(df['Close'], length=20, std=2.0)
        if bb is not None: df['BB_Lower'] = bb[bb.columns[0]]; df['BB_Upper'] = bb[bb.columns[2]]; df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['SMA_20']
        else: df['BB_Lower'] = df['Close']*0.98; df['BB_Upper'] = df['Close']*1.02; df['BB_Width'] = 0.04
        kdj = ta.kdj(df['High'], df['Low'], df['Close']); df['K'], df['D'] = (kdj[kdj.columns[0]], kdj[kdj.columns[1]]) if kdj is not None else (50, 50)
        df['RSI'] = ta.rsi(df['Close'], 14); df['RSI_2'] = ta.rsi(df['Close'], 2)
        adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14); df['ADX'] = adx_df[adx_df.columns[0]] if adx_df is not None else 0
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        st = ta.supertrend(df['High'], df['Low'], df['Close'], length=10, multiplier=3.0)
        if st is not None: df['SuperTrend'], df['SuperTrend_Dir'] = st[st.columns[0]], st[st.columns[1]]
        else: df['SuperTrend'], df['SuperTrend_Dir'] = df['SMA_20'], 1
        
        std_20 = df['Close'].rolling(20).std()
        df['Z_Score'] = (df['Close'] - df['SMA_20']) / (std_20 + 1e-9)
        df['Z_Score'] = df['Z_Score'].fillna(0.0)

        df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3; df['VP'] = df['TP'] * df['Volume']
        df['Date_Group'] = df.index.date; df['Cum_VP'] = df.groupby('Date_Group')['VP'].cumsum(); df['Cum_Vol'] = df.groupby('Date_Group')['Volume'].cumsum()
        df['VWAP'] = df['Cum_VP'] / (df['Cum_Vol'] + 1e-9)
        df['VWAP_Dev'] = (df['Close'] - df['VWAP']).rolling(20).std()
        df['VWAP_Upper'] = df['VWAP'] + 2.0 * df['VWAP_Dev']; df['VWAP_Lower'] = df['VWAP'] - 2.0 * df['VWAP_Dev']
        df['RVOL'] = df['Volume'] / (df['Vol_SMA'] + 1e-9)
        
        current_date = df.index[-1].date()
        today_data = df[df.index.date == current_date]
        if not today_data.empty: 
            df['IB_High'] = today_data['High'].max()
            df['IB_Low'] = today_data['Low'].min()
            df['IB_Defined'] = True
            orb_data = today_data[(today_data.index.time >= dt_time(9, 30)) & (today_data.index.time < dt_time(9, 45))]
            if not orb_data.empty:
                df['ORB_High'] = orb_data['High'].max()
                df['ORB_Low'] = orb_data['Low'].min()
            else:
                df['ORB_High'] = np.nan; df['ORB_Low'] = np.nan
        else: 
            df['IB_High'] = np.nan; df['IB_Low'] = np.nan; df['IB_Defined'] = False
            df['ORB_High'] = np.nan; df['ORB_Low'] = np.nan
            
        return df
    except: return pd.DataFrame()

def get_vix_level():
    try:
        vix = yf.Ticker("^VIX").history(period="1d")
        if not vix.empty: return vix['Close'].iloc[-1]
        return 20.0
    except: return 20.0

class Adaptive_Brain:
    def get_dynamic_weights(self, adx_value, minutes_to_close, rvol, regime, sym, is_hedge, tech_siphon_day, wyckoff_dist, oneil_dryup, chaotic_history, is_hot_sector=False):
        w = {
            'V28_Breakout': 40, 'V29_Shadow': 50, 'V30_VWAP': 45, 'V31_Fader': 50, 'V32_Velocity': 60,
            'V33_Axis': 70, 'V34_SmartMoney': 80, 'V35_Absorption': 90, 'V36_Liquidity': 85, 
            'V37_Delta': 90, 'V38_MeasuredMove': 65, 'V39_ChannelDrive': 75, 'V40_Magnet': 95, 
            'V41_Cluster': 85, 'V42_Fakeout': 999, 'V43_IB': 80
        }
        if regime == "MORNING": w['V28_Breakout'] *= 1.5; w['V32_Velocity'] *= 1.5
        elif regime == "MIDDAY":
            if is_hot_sector: w['V28_Breakout'] *= 1.2
            else: w['V28_Breakout'] = 0
            w['V31_Fader'] *= 2.5; w['V40_Magnet'] = 80
        if adx_value > 25:
            w['V30_VWAP'] *= 2.0; w['V33_Axis'] = 0; w['V40_Magnet'] = 0
        else:
            w['V33_Axis'] *= 2.0; w['V39_ChannelDrive'] *= 2.5; w['V40_Magnet'] *= 1.0
        return w

class Strategy_V28_TrendBreakout:
    def check(self, curr): return (True, "Breakout") if curr['ADX']>25 and curr['Close']>curr['EMA_20'] else (False,"")
class Strategy_V30_VWAP_Retest:
    def check(self, curr, prev): return (True, "VWAP蓄力") if curr['Close']>curr['SMA_200'] and curr['Close']>curr['VWAP'] and curr['Low']<=curr['VWAP']*1.002 else (False,"")
class Strategy_V32_OrderFlow_Velocity:
    def check(self, curr, prev, is_hedge): return (True, "扫货") if curr['Volume']>curr['Vol_SMA']*2.5 and curr['Close']>curr['Open'] else (False,"")
class Strategy_V42_BullTrap_StopSignal:
    def check(self, curr, prev): return (True, "假突防守") if prev['Close']>prev['Open'] and curr['Close']<curr['Open'] and curr['Close']<prev['Open'] else (False,"")

class Quantum_Engine:
    def __init__(self, ib_client):
        self.ib = ib_client
        self.brain = Adaptive_Brain()
        self.params = PARAMS 
        self.high_water_marks = {} 
        self.last_buy_time = {} 
        self.daily_blacklist = set()        
        self.cooldown_ledger = {}           
        self.defense_mode = False           
        
        self.start_of_day_equity = None
        self.daily_max_pnl = 0.0
        self.halt_trading_for_day = False
        self.trading_date = None
        self.black_swan_cooldown = None
        
        # 🚨 V29.87 核心科技：3重毛刺滤震库
        self.pnl_history = []

    def read_radar_intel(self):
        try:
            if not os.path.exists('news_sentiment.json'): return None
            with open('news_sentiment.json', 'r', encoding='utf-8') as f: data = json.load(f)
            intel_time_str = data.get('timestamp', '2000-01-01 00:00:00')[:19]
            intel_time = datetime.strptime(intel_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - intel_time).total_seconds() / 60.0 > 15:
                logger.warning(f"⚠️ 云端情报已断连，自动切断雷达，转为纯技术面盲打！")
                return None
            return data
        except: return None

    def get_account_status(self):
        try:
            tags = self.ib.accountSummary()
            equity = 0.0; total_cash = 0.0
            for tag in tags:
                if tag.tag == 'NetLiquidation': equity = float(tag.value)
                if tag.tag == 'TotalCashValue': total_cash = float(tag.value)
            return equity, total_cash
        except: return 0.0, 0.0

    def liquidate_all_positions(self):
        logger.warning("🚨 执行全账户一键清仓！")
        try:
            for order in self.ib.openOrders(): self.ib.cancelOrder(order)
            self.ib.sleep(1) 
            for p in self.ib.positions():
                if p.position != 0:
                    self.ib.placeOrder(p.contract, MarketOrder('SELL' if p.position > 0 else 'BUY', abs(p.position)))
        except: pass

    def execute_sell_and_lock(self, sym, price, avg_cost, reason):
        if avg_cost > 0:
            if (price - avg_cost) / avg_cost < 0: self.daily_blacklist.add(sym)
            else: self.cooldown_ledger[sym] = datetime.now(timezone.utc)
        self.close_position(sym)

    def close_position(self, symbol):
        try:
            for o in self.ib.openOrders():
                if o.contract.symbol == symbol: self.ib.cancelOrder(o)
            self.ib.sleep(0.5) 
            for p in self.ib.positions():
                if p.contract.symbol == symbol and p.position != 0:
                    self.ib.placeOrder(p.contract, MarketOrder('SELL' if p.position > 0 else 'BUY', abs(p.position)))
        except: pass

    def calculate_strategy_score(self, curr, prev, df, is_hedge, minutes_to_close, regime, is_loss_state=False, rebel_mode=False, sym="", tech_siphon_day=False, wyckoff_dist=False, oneil_dryup=False, chaotic_history=False, hot_sector=None):
        adx = curr['ADX']
        rvol = curr['RVOL']
        is_hot_sector_sym = (hot_sector and TARGET_MAP.get(sym) == hot_sector)
        w_map = self.brain.get_dynamic_weights(adx, minutes_to_close, rvol, regime, sym, is_hedge, tech_siphon_day, wyckoff_dist, oneil_dryup, chaotic_history, is_hot_sector_sym)
        
        score = 0
        triggers = []
        if is_hot_sector_sym: score += 25; triggers.append(f"避风港特权({hot_sector})")
        
        s1 = Strategy_V28_TrendBreakout(); h, m = s1.check(curr)
        if h: score += w_map.get('V28_Breakout', 0); triggers.append(m)
        s2 = Strategy_V30_VWAP_Retest(); h, m = s2.check(curr, prev)
        if h: score += w_map.get('V30_VWAP', 0); triggers.append(m)
        s3 = Strategy_V32_OrderFlow_Velocity(); h, m = s3.check(curr, prev, is_hedge)
        if h: score += w_map.get('V32_Velocity', 0); triggers.append(m)
        
        return score, triggers

    def get_dynamic_pos_size(self, score):
        if score >= 90: return 0.20    
        elif score >= 75: return 0.12  
        elif score >= 55: return 0.08  
        else: return 0.00              

    def run_cycle(self):
        try:
            minutes_to_close, tag_msg, is_market_open, regime = get_market_status_and_regime()
            if not is_market_open: return time.sleep(60)
                
            us_eastern = pytz.timezone('US/Eastern')
            vix_level = get_vix_level()
            vix_multiplier = max(0.1, 20.0 / max(10.0, vix_level))

            positions = {p.contract.symbol: (float(p.position), float(p.avgCost)) for p in self.ib.positions()}
            pos_symbols = list(positions.keys())
            scan_list = list(set(TARGET_MAP.keys()).union(set(pos_symbols)))

            equity, total_cash = self.get_account_status()
            
            current_date_str = datetime.now(us_eastern).strftime('%Y-%m-%d')
            if self.trading_date != current_date_str and equity > 0:
                self.trading_date = current_date_str
                self.start_of_day_equity = equity
                self.daily_max_pnl = 0.0
                self.halt_trading_for_day = False
                self.pnl_history.clear() # 每日清空毛刺记忆
                logger.info(f"🌅 新交易日开始，状态机已归零。记录初始净值: ${self.start_of_day_equity:.2f}")

            if self.halt_trading_for_day:
                logger.info(f"🔒 日内利润锁已触发，今日停止开新仓，锁定胜局！")
                time.sleep(60)
                return

            intel = self.read_radar_intel()
            sentiment_scores = {}
            if intel:
                sentiment_scores = intel.get('stock_sentiment', {})
                if intel.get('emergency_halt', False):
                    self.liquidate_all_positions()
                    self.halt_trading_for_day = True
                    return

            # ==============================================================
            # 🚨 V29.88 核心进阶：智能动态滤震水位线系统 (基于本金1% + 大盘趋势判定)
            # ==============================================================
            # 提前抓取大盘数据，赋予机器人“看大盘下菜碟”的思维
            spy_df = get_data_realtime_ibkr("SPY")
            spy_is_strong = False
            spy_is_weak = False
            hot_sector = None
            
            if not spy_df.empty:
                spy_curr = spy_df.iloc[-1]
                spy_vwap = spy_curr.get('VWAP', spy_curr['Close'])
                spy_sma20 = spy_curr.get('SMA_20', spy_curr['Close'])
                
                # 判定大盘强弱
                if spy_curr['Close'] > spy_vwap and spy_curr['Close'] > spy_sma20:
                    spy_is_strong = True
                elif spy_curr['Close'] < spy_vwap and spy_curr['Close'] < spy_sma20:
                    spy_is_weak = True

                # 宏观板块轮动雷达 (避风港)
                sector_returns = {}
                for s_etf in ["XLK", "XLE", "XLF", "GLD", "XLU", "XLC", "XLY"]:
                    s_df = get_data_realtime_ibkr(s_etf)
                    if not s_df.empty and s_df['Open'].iloc[-1] > 0:
                        s_curr = s_df.iloc[-1]
                        s_ret = (s_curr['Close'] - s_curr['Open']) / s_curr['Open']
                        if s_ret > 0.002 and s_curr['Close'] > s_curr.get('VWAP', s_curr['Close']):
                            sector_returns[s_etf] = s_ret
                if sector_returns:
                    hot_sector = max(sector_returns, key=sector_returns.get)

            current_pnl = 0.0
            if self.start_of_day_equity and equity > 0:
                current_pnl = equity - self.start_of_day_equity
                
                # 记录最新的 PNL 到历史库中（最多保留最近 3 次探测）
                self.pnl_history.append(current_pnl)
                if len(self.pnl_history) > 3:
                    self.pnl_history.pop(0)
                
                # 计算稳态利润：彻底剥离一秒钟的报价毛刺！
                stable_pnl = min(self.pnl_history) if len(self.pnl_history) == 3 else current_pnl

                nyc_time_now = datetime.now(us_eastern).time()
                is_early_morning = nyc_time_now < dt_time(9, 33)
                
                # 动态目标：基于真实本金的 1%
                dynamic_target_pnl = self.start_of_day_equity * self.params.get('DAILY_TARGET_PCT', 0.01)

                if not is_early_morning:
                    # 只有稳态利润创新高，才承认最高水位线
                    if stable_pnl > self.daily_max_pnl: 
                        self.daily_max_pnl = stable_pnl

                    # 机器人的“思考”：达到本金1%后，不再死板平仓，而是根据大盘决定回撤容忍度
                    if self.daily_max_pnl >= dynamic_target_pnl:
                        if spy_is_strong:
                            tolerance = self.params.get('TRAILING_TOLERANCE_BULL', 0.35)
                            tag = "🐂大盘强势(放宽35%回撤，让利润奔跑)"
                        elif spy_is_weak:
                            tolerance = self.params.get('TRAILING_TOLERANCE_BEAR', 0.15)
                            tag = "🐻大盘弱势(收紧15%回撤，落袋为安)"
                        else:
                            tolerance = self.params.get('TRAILING_TOLERANCE_NORMAL', 0.25)
                            tag = "⚖️大盘震荡(标准25%回撤)"
                            
                        lock_val = self.daily_max_pnl * (1.0 - tolerance)
                        
                        if stable_pnl < lock_val:
                            logger.error(f"🛑 智能追踪锁: 稳态利润已达标(本金1%), 当前{tag}。最高利润 ${self.daily_max_pnl:.0f}，回撤跌破防线 ${lock_val:.0f}！全仓止盈！")
                            self.liquidate_all_positions()
                            self.halt_trading_for_day = True
                            return
                            
                    # 恢复您要求的细节：利润护城河（防守模式）
                    half_target = dynamic_target_pnl * 0.5
                    if self.daily_max_pnl >= half_target and stable_pnl < self.daily_max_pnl * 0.70:
                        if not self.defense_mode:
                            logger.warning(f"🛡️ 护城河警报: 利润回撤达30%，强制切入【半仓高门槛防守模式】！")
                            self.defense_mode = True
                    if self.defense_mode and stable_pnl >= self.daily_max_pnl * 0.90:
                        logger.info(f"🔓 自我救赎成功: 利润已收复高点的90%，解除防守，重归【满血全攻】！")
                        self.defense_mode = False
                else:
                    if self.daily_max_pnl > 0 or current_pnl != 0:
                        pass # 早盘3分钟不看回撤
            # ==============================================================

            virtual_positions = set(pos_symbols)
            virtual_cash = total_cash
            
            logger.info(f"🔍 V29.86 -> V29.87 | {tag_msg} | 稳态P&L: ${stable_pnl:.0f} (最高: ${self.daily_max_pnl:.0f})")
            
            bull_trap_stop_strat = Strategy_V42_BullTrap_StopSignal()

            for sym in scan_list:
                try: 
                    for order in self.ib.openOrders():
                        if order.contract.symbol == sym and order.action == 'BUY':
                            self.ib.cancelOrder(order)
                    
                    if sym in self.daily_blacklist and sym not in virtual_positions: continue
                    if sym in self.cooldown_ledger and sym not in virtual_positions:
                        if (datetime.now(timezone.utc) - self.cooldown_ledger[sym]).total_seconds() < 1800: continue
                        else: del self.cooldown_ledger[sym]
                    
                    df = get_data_realtime_ibkr(sym) 
                    if df.empty or len(df) < 50: continue
                    curr = df.iloc[-1]; prev = df.iloc[-2]; price = curr['Close']
                    is_hedge = sym in HEDGE_TARGETS

                    # 🛡️ 持仓防守
                    sold_this_tick = False
                    if sym in positions and sym not in virtual_positions: continue
                    if sym in positions:
                        qty, avg_cost = positions[sym]
                        if sym not in self.high_water_marks: self.high_water_marks[sym] = max(price, avg_cost)
                        else: self.high_water_marks[sym] = max(price, self.high_water_marks[sym])
                        highest = self.high_water_marks[sym]
                        ret = (price - avg_cost) / avg_cost
                        max_ret = (highest - avg_cost) / avg_cost
                        
                        last_buy = self.last_buy_time.get(sym, datetime.min.replace(tzinfo=timezone.utc))
                        time_since_buy = (datetime.now(timezone.utc) - last_buy).total_seconds()
                        is_immune = time_since_buy < self.params['NEWBORN_IMMUNITY_SEC'] 

                        if not is_immune and not sold_this_tick:
                            is_bull_trap, msg = bull_trap_stop_strat.check(curr, prev)
                            if is_bull_trap: 
                                self.execute_sell_and_lock(sym, price, avg_cost, f"逃顶防守-{msg}")
                                virtual_positions.discard(sym); sold_this_tick = True
                                
                        if not sold_this_tick:
                            atr = curr['ATR'] if not np.isnan(curr['ATR']) else price * 0.02
                            stop_price = avg_cost - (atr * self.params['ATR_STOP_MULT'])
                            if max_ret >= 0.015: stop_price = avg_cost * 1.002
                            if price < stop_price:
                                self.execute_sell_and_lock(sym, price, avg_cost, "ATR硬止损")
                                virtual_positions.discard(sym); sold_this_tick = True

                    if sold_this_tick: continue

                    # ⚔️ 进攻侦察
                    score, triggers = self.calculate_strategy_score(curr, prev, df, is_hedge, minutes_to_close, regime, False, False, sym, False, False, False, False, hot_sector)
                    
                    if intel and sym in sentiment_scores:
                        nlp_score = sentiment_scores[sym]
                        if nlp_score >= 0.3: score += 15; triggers.append("AI利好")
                        elif nlp_score <= -0.3: score -= 25; triggers.append("AI利空")
                    
                    if score >= self.params['MIN_SCORE_TO_BUY']:
                        atr = curr['ATR'] if not np.isnan(curr['ATR']) else price * 0.02
                        current_qty = int(positions[sym][0]) if sym in positions else 0
                        avg_cost = float(positions[sym][1]) if sym in positions else 0.0
                        
                        dynamic_pos_pct = self.get_dynamic_pos_size(score) * vix_multiplier
                        target_qty = int((equity * dynamic_pos_pct) / price)
                        qty_to_buy = target_qty - current_qty
                        
                        if qty_to_buy > 0:
                            if current_qty > 0 and (price - avg_cost)/avg_cost <= 0: qty_to_buy = 0 
                            
                            cost = qty_to_buy * price
                            if cost > (virtual_cash - equity * CASH_RESERVE): qty_to_buy = int((virtual_cash - equity * CASH_RESERVE) / price)
                            
                            if qty_to_buy * price >= self.params['MIN_ORDER_USD']:
                                logger.info(f"🚀 行动: {sym} | 得分:{score} | 加买Qty:{qty_to_buy} | {','.join(triggers)}")
                                contract = Stock(sym, 'SMART', 'USD')
                                order = LimitOrder('BUY', qty_to_buy, round(price * 1.005, 2))
                                self.ib.placeOrder(contract, order)
                                
                                virtual_cash -= qty_to_buy * price
                                virtual_positions.add(sym)
                                self.last_buy_time[sym] = datetime.now(timezone.utc)
                
                except Exception as e:
                    logger.error(f"❌ 处理出错 {sym}: {e}")
                    continue

        except Exception as outer_e:
            logger.error(f"🚨 主循环异常: {outer_e}")
            self.ib.sleep(5)

if __name__ == "__main__":
    if not ib.isConnected(): connect_ib()
    engine = Quantum_Engine(ib)
    try:
        while True:
            engine.run_cycle()
            logger.info("⏳ 等待 1分钟...") 
            ib.sleep(60) 
    except KeyboardInterrupt: 
        ib.disconnect()
        logger.info("👋 已断开连接")