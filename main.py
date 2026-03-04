import os
import json
import logging
import time
import threading
from datetime import datetime, timezone
import feedparser
from openai import OpenAI
from fastapi import FastAPI
import uvicorn

# ================= 🔧 核心配置区 =================
# 🛡️ 军用级安全：从 Railway 环境变量读取密钥，绝不触发 GitHub 拦截
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

# 🎯 监控标的池 (已与 V29 战车 100% 对齐)
STOCKS = [
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MSFT", "GOOGL", "META", "AMZN", "PLTR",
    "AAPL", "NFLX", "ADBE", "MU", "INTC", "QCOM", "TSLA",
    "MSTR", "COIN", "IBIT", "LLY", "NVO",
    "VST", "CEG", "NRG", "GEV", "CAT", "WMT", "COST", "XOM", "CVX",
    "JPM", "V", "MA", "BRK.B", "GE", "RTX", "LMT", "WM",
    "NEM", "FCX", "GLD", "IAU"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 大龙虾2.0 (FastAPI终极版) - %(message)s', datefmt='%H:%M:%S')
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
    if not OPENAI_API_KEY:
        logger.error("🚨 致命错误：未配置 OPENAI_API_KEY！请在 Railway 控制台 Variables 中添加。")
        return None

    prompt = f"""你现在是华尔街最顶尖的宏观对冲基金经理兼量化策略师。
我将为你提供过去几小时内美股和全球宏观的最新新闻头条。
你需要深刻理解“资金轮动、地缘政治博弈、美元指数潮汐、跨资产传导”等高级金融逻辑。

【任务要求】：
阅读新闻，推演对板块和个股的情绪影响。
输出必须是纯粹的 JSON 格式数据。

预期 JSON 结构如下：
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
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            # 🚀 终极武器：强制 API 仅返回标准的 JSON 对象，彻底消灭 JSONDecodeError
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a professional Wall Street algorithmic trading AI. You must output strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        
        # 强制 JSON 模式下，必定返回完美的 JSON 字符串，直接解析即可
        result_text = response.choices[0].message.content.strip()
        return json.loads(result_text)
            
    except Exception as e:
        logger.error(f"❌ GPT-4 调用或 JSON 解析失败: {e}")
        return None

# ================= ⚙️ 经典稳定版 FastAPI 框架核心 =================
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
    """最传统的后台死循环线程，在 Railway 上绝不卡死主程序"""
    global latest_intel
    logger.info("🚀 GPT-4 脑核心后台线程已点火...")
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
                    logger.info("✅ 宏观情绪 JSON 已成功提取并存入内存！")
        except Exception as e:
            logger.error(f"后台刷新异常: {e}")
            
        time.sleep(FETCH_INTERVAL_MINUTES * 60)

@app.on_event("startup")
def startup_event():
    # 使用独立的线程运行爬虫和GPT，绝不堵塞 Web 端口
    t = threading.Thread(target=background_worker, daemon=True)
    t.start()

# 正常大门
@app.get('/')
def get_intel():
    return latest_intel

# 🚀 绝杀 404 错误：开启全路径万能拦截网！
# 无论 Courier_Bot.py 访问 /news_sentiment.json 还是其他旁门左道，都强制把情报塞给它！
@app.get('/{catchall:path}')
def get_intel_catchall(catchall: str):
    return latest_intel

if __name__ == "__main__":
    # 保留给本地测试的入口，Railway 将使用 Procfile 启动
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host='0.0.0.0', port=port)