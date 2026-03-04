import os
import json
import time
import threading
import logging
import re
from datetime import datetime, timezone
import feedparser
from openai import OpenAI
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

# ================= 🔧 核心配置区 =================
# 🚨 彻底移除了带有特征的伪造占位符，防止 GitHub 安全拦截导致“上传失败”！
# 必须在 Railway 控制台的 Variables 中配置真实密钥
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL_NAME = "gpt-4o"  
FETCH_INTERVAL_MINUTES = 15  

RSS_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", 
    "https://www.investing.com/rss/news_25.rss", 
    "https://www.investing.com/rss/commodities.rss", 
    "https://finance.yahoo.com/news/rssindex" 
]

# 🎯 监控标的池 (已与 V29.86 战车 100% 对齐)
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
        # 确保环境变量中有 Key
        if not OPENAI_API_KEY:
            logger.error("🚨 致命错误：未配置 OPENAI_API_KEY！请在 Railway 环境变量中添加。")
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
        
        # 🚀 军用级 JSON 提取：使用正则表达式精准捕获大括号内容，无视 GPT 返回的任何多余字符
        match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if match:
            clean_json = match.group(0)
            return json.loads(clean_json)
        else:
            logger.error("❌ 无法从 GPT-4 回复中提取有效的 JSON 结构。")
            return None
            
    except Exception as e:
        logger.error(f"❌ GPT-4 调用或解析失败: {e}")
        return None

# ================= ⚙️ 原始 FastAPI 框架核心 =================
latest_intel = {
    "emergency_halt": False,
    "macro_sentiment": 0.0,
    "sector_sentiment": {},
    "stock_sentiment": {},
    "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    "status": "Initializing Engine..."
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
                    data['status'] = "Online - GPT-4 Engine Active"
                    latest_intel = data
                    logger.info("✅ 情报已更新并存入内存")
        except Exception as e:
            logger.error(f"刷新异常: {e}")
        time.sleep(FETCH_INTERVAL_MINUTES * 60)

# 现代化升级：使用 lifespan 管理后台进程
@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=background_task, daemon=True)
    t.start()
    yield

app = FastAPI(lifespan=lifespan)

# 🚀 异步化升级：极速响应，告别 Read timed out
@app.get('/')
async def get_intel():
    """本地访问接口"""
    return latest_intel

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host='0.0.0.0', port=port)