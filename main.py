import os
import json
import logging
import re
import time
import threading
from datetime import datetime, timezone
import feedparser
from openai import OpenAI
from fastapi import FastAPI
import uvicorn

# ================= 🔧 核心配置区 =================
MODEL_NAME = "gpt-4o"  
FETCH_INTERVAL_MINUTES = 15  

RSS_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", 
    "https://www.investing.com/rss/news_25.rss", 
    "https://www.investing.com/rss/commodities.rss", 
    "https://finance.yahoo.com/news/rssindex" 
]

# 🎯 监控标的池 (与 V29.86 100% 对齐)
STOCKS = [
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MSFT", "GOOGL", "META", "AMZN", "PLTR",
    "AAPL", "NFLX", "ADBE", "MU", "INTC", "QCOM", "TSLA",
    "MSTR", "COIN", "IBIT", "LLY", "NVO",
    "VST", "CEG", "NRG", "GEV", "CAT", "WMT", "COST", "XOM", "CVX",
    "JPM", "V", "MA", "BRK.B", "GE", "RTX", "LMT", "WM",
    "NEM", "FCX", "GLD", "IAU"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 大龙虾2.0 (FastAPI经典版) - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger()

# ================= 🧠 GPT-4 宏观推演引擎 =================
def fetch_global_news():
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                headlines.append(f"- {entry.title}: {entry.get('summary', '')[:100]}")
        except Exception:
            pass
    return headlines

def call_gpt4_financial_brain(news_text):
    # 每次调用时动态读取，确保能读到 Railway 的环境变量
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("🚨 致命错误：未配置 OPENAI_API_KEY！")
        return None

    prompt = f"""你现在是华尔街最顶尖的宏观对冲基金经理兼量化策略师。
我将为你提供过去几小时内美股和全球宏观的最新新闻头条。
你需要深刻理解“资金轮动、地缘政治博弈、美元指数潮汐、跨资产传导”等高级金融逻辑。

【任务要求】：
阅读新闻，推演对板块和个股的情绪影响。
输出必须是纯粹的 JSON 格式，绝对不要包含任何注释符(//)或Markdown标记：

{{
  "emergency_halt": false,
  "macro_sentiment": 0.0,
  "sector_sentiment": {{
    "XLK": 0.0, "XLE": 0.0, "GLD": 0.0, "XLF": 0.0, "XLU": 0.0
  }},
  "stock_sentiment": {{
     "NVDA": 0.5,
     "XOM": -0.3
  }}
}}

注意：stock_sentiment 中的股票必须只能从以下名单中挑选并打分(-1.0到1.0)：
{', '.join(STOCKS)}

【最新全球新闻】：
{news_text}
"""
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You output strict, valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        result_text = response.choices[0].message.content.strip()
        
        # 军用级 JSON 提取
        match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            return None
    except Exception as e:
        logger.error(f"❌ GPT-4 调用失败: {e}")
        return None

# ================= ⚙️ 经典 FastAPI 框架核心 =================
app = FastAPI()

latest_intel = {
    "emergency_halt": False,
    "macro_sentiment": 0.0,
    "sector_sentiment": {},
    "stock_sentiment": {},
    "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    "status": "Initializing Engine..."
}

def background_worker():
    """最传统的后台死循环线程，绝不卡死主程序"""
    global latest_intel
    logger.info("🚀 GPT-4 脑核心传统后台线程已点火...")
    while True:
        try:
            headlines = fetch_global_news()
            if headlines:
                news_text = "\n".join(headlines)
                data = call_gpt4_financial_brain(news_text)
                if data:
                    data['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    data['status'] = "Online - GPT-4 Engine Active"
                    latest_intel = data
                    logger.info("✅ 情报已更新并存入内存")
        except Exception as e:
            logger.error(f"后台刷新异常: {e}")
            
        time.sleep(FETCH_INTERVAL_MINUTES * 60)

# 恢复最初始、最稳定的启动机制
@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=background_worker, daemon=True)
    t.start()

@app.get('/')
def get_intel():
    return latest_intel