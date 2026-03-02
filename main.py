import os
import time
import asyncio
import logging
from datetime import datetime
import feedparser
from fastapi import FastAPI
import uvicorn
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- 系统配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Lobster Radar NLP Engine V3.0 (WallStreet Edition)")
analyzer = SentimentIntensityAnalyzer()

# --- 狙击目标池 ---
STOCK_POOL = [
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MU", "INTC", "QCOM", "AAPL", "MSFT", 
    "GOOGL", "META", "AMZN", "NFLX", "ADBE", "PLTR", "CVX", "XOM", "VST", "CEG", 
    "NRG", "GEV", "NEM", "FCX", "LLY", "NVO", "MSTR", "COIN", "JPM", "V", "MA", 
    "BRK.B", "GE", "RTX", "LMT", "WM", "CAT", "COST", "WMT"
]

SECTOR_POOL = ["SPY", "QQQ", "XLK", "XLE", "XLF", "GLD"]

# ================= 🛡️ 智能上下文 NLP 过滤系统 =================
FALSE_ALARMS = [
    "price war", "bidding war", "talent war", "culture war", 
    "war on inflation", "war on drugs", "streaming war", "cloud war"
]

GEO_ACTORS = [
    "russia", "ukraine", "nato", "china", "taiwan", "iran", "israel", 
    "middle east", "north korea", "us military", "pentagon"
]

CONFLICT_ACTIONS = [
    "war", "missile", "airstrike", "invasion", "troops", "nuclear", "assassination"
]

FINANCIAL_NUKES = [
    "emergency rate cut", "stock market crash", "trading halted", "limit down"
]

def check_black_swan(text: str) -> bool:
    """第一防线：只拦截真正的毁灭级黑天鹅 (触发全仓清空)"""
    if not text: return False
    t = text.lower()
    
    if any(nuke in t for nuke in FINANCIAL_NUKES): return True
    
    is_fake_war = any(fake in t for fake in FALSE_ALARMS)
    has_action = any(action in t for action in CONFLICT_ACTIONS)
    
    if has_action and not is_fake_war:
        has_actor = any(actor in t for actor in GEO_ACTORS)
        if has_actor: return True
            
    return False

# ================= 📈 专业金融催化剂评分引擎 =================
# 当出现以下词汇时，直接暴增或暴扣该股票的独立分数，指导 V29.82 单独重仓或割肉！

EARNINGS_BULLISH = [
    "beat estimates", "guidance raised", "strong earnings", "revenue growth", 
    "profit surge", "dividend raised", "record high", "share buyback"
]

EARNINGS_BEARISH = [
    "miss estimates", "guidance cut", "weak earnings", "revenue fell", 
    "profit warning", "disappointing", "downgraded"
]

MACRO_BEARISH = [
    "tariff", "trade war", "sanctions", "export controls", "embargo", 
    "antitrust probe", "sec investigation"
]

def calculate_financial_score(text: str) -> float:
    """第二防线：为 V29.82 输出精确到个股的买卖强度分数"""
    t = text.lower()
    # 基础通用 NLP 情感得分 (-1.0 到 1.0)
    base_score = analyzer.polarity_scores(text)['compound']
    
    # 华尔街术语暴击加成
    if any(word in t for word in EARNINGS_BULLISH):
        base_score += 0.5  # 财报超预期，分数强行拉高，确保 V29.82 追涨
        
    if any(word in t for word in EARNINGS_BEARISH):
        base_score -= 0.5  # 财报爆雷，分数强行踩死，确保 V29.82 割肉
        
    if any(word in t for word in MACRO_BEARISH):
        base_score -= 0.6  # 遭遇关税/贸易战/制裁，分数踩死，甚至可以做空
        
    # 限制分数在 -1.0 到 1.0 之间
    return max(-1.0, min(1.0, base_score))

# ==============================================================

current_sentiment = {
    "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
    "macro_sentiment": 0.0,
    "sector_sentiment": {s: 0.0 for s in SECTOR_POOL},
    "stock_sentiment": {s: 0.0 for s in STOCK_POOL},
    "emergency_halt": False
}

def fetch_and_analyze_sync():
    global current_sentiment
    logger.info("🦞 大龙虾雷达启动：金融级深度扫描中...")
    
    emergency_triggered = False
    new_macro_scores = []
    new_sector_sentiment = {}
    new_stock_sentiment = {}

    try:
        # 1. 扫描板块
        for sector in SECTOR_POOL:
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sector}"
            feed = feedparser.parse(url)
            scores = []
            for entry in feed.entries[:5]: 
                text = f"{entry.title} {entry.get('summary', '')}"
                if check_black_swan(text):
                    emergency_triggered = True
                    logger.warning(f"🚨 真实黑天鹅警报触发! 来源: {sector} -> {entry.title}")
                scores.append(calculate_financial_score(text)) # 使用全新的金融打分器
            
            avg_score = sum(scores) / len(scores) if scores else 0.0
            new_sector_sentiment[sector] = round(avg_score, 3)
            new_macro_scores.extend(scores)
            time.sleep(0.5) 

        # 2. 扫描个股
        for stock in STOCK_POOL:
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={stock}"
            feed = feedparser.parse(url)
            scores = []
            for entry in feed.entries[:5]:
                text = f"{entry.title}"
                if check_black_swan(text):
                    emergency_triggered = True
                    logger.warning(f"🚨 真实黑天鹅警报触发! 来源: {stock} -> {entry.title}")
                scores.append(calculate_financial_score(text)) # 使用全新的金融打分器
                
            avg_score = sum(scores) / len(scores) if scores else 0.0
            new_stock_sentiment[stock] = round(avg_score, 3)
            time.sleep(0.5)

        # 3. 数据注入
        macro_avg = sum(new_macro_scores) / len(new_macro_scores) if new_macro_scores else 0.0
        
        current_sentiment["timestamp"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S (UTC)')
        current_sentiment["macro_sentiment"] = round(macro_avg, 3)
        current_sentiment["sector_sentiment"] = new_sector_sentiment
        current_sentiment["stock_sentiment"] = new_stock_sentiment
        
        if emergency_triggered:
            current_sentiment["emergency_halt"] = True
            
        logger.info(f"✅ 扫描完成。宏观情绪: {macro_avg:.3f} | 黑天鹅状态: {current_sentiment['emergency_halt']}")

    except Exception as e:
        logger.error(f"❌ 爬虫异常: {e}")

async def radar_loop():
    while True:
        await asyncio.to_thread(fetch_and_analyze_sync)
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(radar_loop())

@app.get("/")
def read_root():
    return {"status": "🦞 Lobster Radar V3 Online. WallStreet Financial Engine Active."}

@app.get("/sentiment")
def get_sentiment():
    return current_sentiment

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)