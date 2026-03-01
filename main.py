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

app = FastAPI(title="Lobster Radar NLP Engine")
analyzer = SentimentIntensityAnalyzer()

# --- 狙击目标池 ---
STOCK_POOL = [
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MU", "INTC", "QCOM", "AAPL", "MSFT", 
    "GOOGL", "META", "AMZN", "NFLX", "ADBE", "PLTR", "CVX", "XOM", "VST", "CEG", 
    "NRG", "GEV", "NEM", "FCX", "LLY", "NVO", "MSTR", "COIN", "JPM", "V", "MA", 
    "BRK.B", "GE", "RTX", "LMT", "WM", "CAT", "COST", "WMT"
]

SECTOR_POOL = ["SPY", "QQQ", "XLK", "XLE", "XLF", "GLD"]

BLACK_SWAN_KEYWORDS = [
    "war", "crash", "emergency rate cut", "meltdown", "nuclear", 
    "pandemic", "black swan", "bankruptcy", "collapse"
]

# --- 全局情报容器 ---
current_sentiment = {
    "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
    "macro_sentiment": 0.0,
    "sector_sentiment": {s: 0.0 for s in SECTOR_POOL},
    "stock_sentiment": {s: 0.0 for s in STOCK_POOL},
    "emergency_halt": False
}

def check_black_swan(text: str) -> bool:
    """核弹探测仪：扫描文本中是否包含极端恐慌词汇"""
    if not text:
        return False
    text_lower = text.lower()
    for kw in BLACK_SWAN_KEYWORDS:
        if kw in text_lower:
            return True
    return False

def fetch_and_analyze_sync():
    """同步阻塞的爬虫与打分逻辑（交由后台线程运行）"""
    global current_sentiment
    logger.info("🦞 大龙虾雷达启动：开始新一轮全网扫描...")
    
    emergency_triggered = False
    new_macro_scores = []
    new_sector_sentiment = {}
    new_stock_sentiment = {}

    try:
        # 1. 扫描板块与宏观情绪
        for sector in SECTOR_POOL:
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sector}"
            feed = feedparser.parse(url)
            scores = []
            for entry in feed.entries[:5]: # 只看最新5条头条
                text = f"{entry.title} {entry.get('summary', '')}"
                if check_black_swan(text):
                    emergency_triggered = True
                    logger.warning(f"🚨 黑天鹅警报触发! 来源: {sector} -> {entry.title}")
                scores.append(analyzer.polarity_scores(text)['compound'])
            
            avg_score = sum(scores) / len(scores) if scores else 0.0
            new_sector_sentiment[sector] = round(avg_score, 3)
            new_macro_scores.extend(scores)
            time.sleep(0.5) # 极度温柔的访问间隔，防封锁

        # 2. 扫描个股微观情绪
        for stock in STOCK_POOL:
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={stock}"
            feed = feedparser.parse(url)
            scores = []
            for entry in feed.entries[:5]:
                text = f"{entry.title}"
                if check_black_swan(text):
                    emergency_triggered = True
                    logger.warning(f"🚨 黑天鹅警报触发! 来源: {stock} -> {entry.title}")
                scores.append(analyzer.polarity_scores(text)['compound'])
                
            avg_score = sum(scores) / len(scores) if scores else 0.0
            new_stock_sentiment[stock] = round(avg_score, 3)
            time.sleep(0.5)

        # 3. 统计并注入全局字典 (加锁更新)
        macro_avg = sum(new_macro_scores) / len(new_macro_scores) if new_macro_scores else 0.0
        
        current_sentiment["timestamp"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S (UTC)')
        current_sentiment["macro_sentiment"] = round(macro_avg, 3)
        current_sentiment["sector_sentiment"] = new_sector_sentiment
        current_sentiment["stock_sentiment"] = new_stock_sentiment
        
        # 只有当发现黑天鹅时才修改为True，如果没发现，且之前是False，保持False
        if emergency_triggered:
            current_sentiment["emergency_halt"] = True
            
        logger.info(f"✅ 扫描完成。当前宏观情绪: {macro_avg:.3f} | 黑天鹅状态: {current_sentiment['emergency_halt']}")

    except Exception as e:
        logger.error(f"❌ 爬虫或打分模块发生异常: {e}")

async def radar_loop():
    """雷达无限循环：每隔10分钟扫描一次"""
    while True:
        # 使用 asyncio.to_thread 防止阻塞 FastAPI 的主线程
        await asyncio.to_thread(fetch_and_analyze_sync)
        # 休息 600 秒 (10分钟)
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    """FastAPI 启动时，同时唤醒后台雷达"""
    asyncio.create_task(radar_loop())

@app.get("/")
def read_root():
    return {"status": "🦞 Lobster Radar is Online. Go to /sentiment to fetch data."}

@app.get("/sentiment")
def get_sentiment():
    """对外数据投递接口"""
    return current_sentiment

if __name__ == "__main__":
    # Railway 强制要求的端口获取方式
    port = int(os.environ.get("PORT", 8080))
    # 强制绑定 0.0.0.0 允许公网访问
    uvicorn.run(app, host="0.0.0.0", port=port)