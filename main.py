import os
import json
import time
import threading
import logging
from datetime import datetime, timezone
import feedparser
from openai import OpenAI
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

# ================= 🔧 核心配置区 =================
# 🚨 修复 API 逻辑：优先读取 Railway 环境变量。如果本地测试，再读取后面的字符串。
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or "sk-proj-请在这里填入您的API密钥"
MODEL_NAME = "gpt-4o"  
FETCH_INTERVAL_MINUTES = 15  

RSS_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", 
    "https://www.investing.com/rss/news_25.rss", 
    "https://www.investing.com/rss/commodities.rss", 
    "https://finance.yahoo.com/news/rssindex" 
]

# 🎯 监控标的池 (已与 V29.86 战车的 Nobles, Commoners, Hedge Targets 100% 对齐)
STOCKS = [
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MSFT", "GOOGL", "META", "AMZN", "PLTR",
    "AAPL", "NFLX", "ADBE", "MU", "INTC", "QCOM", "TSLA",
    "MSTR", "COIN", "IBIT", "LLY", "NVO",
    "VST", "CEG", "NRG", "GEV", "CAT", "WMT", "COST", "XOM", "CVX",
    "JPM", "V", "MA", "BRK.B", "GE", "RTX", "LMT", "WM",
    "NEM", "FCX", "GLD", "IAU"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 大龙虾2.0 (FastAPI版) - %(message)s', datefmt='%H:%M:%S')
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
    # 🚨 修复 JSON BUG：彻底清除了模板中的所有注释，防止 json.loads 解析崩溃！
    prompt = f"""
你现在是华尔街最顶尖的宏观对冲基金经理兼量化策略师。
我将为你提供过去几小时内美股和全球宏观的最新新闻头条。
你需要深刻理解“资金轮动、地缘政治博弈、美元指数潮汐、跨资产传导”等高级金融逻辑。

【任务要求】：
阅读以下新闻，推演对具体板块和个股的情绪影响。
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
        # 防呆机制：确保 Key 正确存在
        if not OPENAI_API_KEY or "请在这里填入" in OPENAI_API_KEY:
            logger.error("🚨 致命错误：未正确配置 OPENAI_API_KEY！将停止推演。")
            return None
            
        client = OpenAI(api_key=OPENAI_API_KEY)
        
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
        
        if result_text.startswith("```json"): 
            result_text = result_text[7:]
        elif result_text.startswith("```"):
            result_text = result_text[3:]
            
        if result_text.endswith("```"): 
            result_text = result_text[:-3]
            
        return json.loads(result_text)
    except json.JSONDecodeError as je:
        logger.error(f"❌ JSON 解析失败，GPT-4 可能未按要求格式输出: {je}\n原始输出: {result_text}")
        return None
    except Exception as e:
        logger.error(f"❌ GPT-4 调用失败: {e}")
        return None

# ================= ⚙️ 原始 FastAPI 框架核心 =================
latest_intel = {
    "emergency_halt": False,
    "macro_sentiment": 0.0,
    "sector_sentiment": {},
    "stock_sentiment": {},
    "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    "status": "Initializing..."
}

def background_task():
    """后台定时刷新机制"""
    global latest_intel
    logger.info("🚀 GPT-4 脑核心后台线程启动...")
    while True:
        try:
            headlines = fetch_global_news()
            if headlines:
                news_text = "\n".join(headlines)
                data = call_gpt4_financial_brain(news_text)
                if data:
                    data['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    data['status'] = "Online"
                    latest_intel = data
                    logger.info("✅ 情报已更新并存入内存")
        except Exception as e:
            logger.error(f"刷新异常: {e}")
        time.sleep(FETCH_INTERVAL_MINUTES * 60)

# 🚨 现代化升级：使用 lifespan 替代废弃的 on_event，防止 Railway 部署时卡死
@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=background_task, daemon=True)
    t.start()
    yield

app = FastAPI(lifespan=lifespan)

@app.get('/')
def get_intel():
    """保留了您上午正常运行的 Web 接口"""
    return latest_intel

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host='0.0.0.0', port=port)