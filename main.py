import os
import json
import time
import logging
import threading
from datetime import datetime, timezone
import feedparser
from openai import OpenAI
from flask import Flask, jsonify

# ================= 🔧 云端系统配置 =================
# 🛡️ 军用级安全：从 Railway 的环境变量中动态读取 API KEY，绝不明文暴露！
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("🚨 致命错误：找不到 OPENAI_API_KEY！请务必在 Railway 后台的 Variables 页面配置此密钥！")

MODEL_NAME = "gpt-4o"  # 核心大脑
FETCH_INTERVAL_MINUTES = 15  # 每15分钟推演一次

RSS_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", 
    "https://www.investing.com/rss/news_25.rss", 
    "https://www.investing.com/rss/commodities.rss", 
    "https://finance.yahoo.com/news/rssindex" 
]

STOCKS = [
    "NVDA", "AAPL", "MSFT", "AMD", "AVGO", "TSM", "META", "GOOGL", "AMZN",
    "XOM", "CVX", "CEG", "VST", "NRG",
    "JPM", "V", "MA",
    "NEM", "FCX", "MSTR", "COIN", "LLY"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 大龙虾2.0(Railway安全版) - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger()

app = Flask(__name__)

# 全局内存变量，用于向 Courier_Bot.py 投喂数据
latest_intel = {
    "emergency_halt": False,
    "macro_sentiment": 0.0,
    "sector_sentiment": {},
    "stock_sentiment": {},
    "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    "status": "Initializing Engine..."
}

def fetch_global_news():
    logger.info("📡 扫描全球宏观新闻...")
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                headlines.append(f"- {entry.title}: {entry.get('summary', '')[:100]}")
        except Exception:
            pass
    return headlines

def call_gpt4_financial_brain(client, news_text):
    prompt = f"""
你现在是华尔街最顶尖的宏观对冲基金经理兼量化策略师。
我将为你提供过去几小时内美股和全球宏观的最新新闻头条。
你需要深刻理解“资金轮动、地缘政治博弈、美元指数潮汐、跨资产传导”等高级金融逻辑。

【任务要求】：
阅读以下新闻，推演对具体板块和个股的情绪影响。
输出必须是纯粹的 JSON 格式，不要输出任何Markdown标记：

{{
  "emergency_halt": false,
  "macro_sentiment": 0.0,
  "sector_sentiment": {{
    "XLK": 0.0, "XLE": 0.0, "GLD": 0.0, "XLF": 0.0, "XLU": 0.0
  }},
  "stock_sentiment": {{
     // 从 {', '.join(STOCKS)} 中挑选受严重影响的，-1.0到1.0
  }}
}}

【最新全球新闻】：
{news_text}
"""
    try:
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
        if result_text.startswith("