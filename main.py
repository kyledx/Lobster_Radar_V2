import os
import json
import time
import threading
import logging
from datetime import datetime, timezone
import feedparser
from openai import OpenAI
from flask import Flask, jsonify

# ================= 🔧 核心配置区 =================
# ⚠️ 直接将您新生成的 API KEY 填在下面的引号里（请确保 GitHub 仓库是 Private 私有的）
OPENAI_API_KEY = "sk-proj-请在这里填入您的API密钥"
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
    # 科技与芯片贵族
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MSFT", "GOOGL", "META", "AMZN", "PLTR",
    "AAPL", "NFLX", "ADBE", "MU", "INTC", "QCOM", "TSLA",
    # 加密货币与医药
    "MSTR", "COIN", "IBIT", "LLY", "NVO",
    # 能源、公用事业与工业避风港
    "VST", "CEG", "NRG", "GEV", "CAT", "WMT", "COST", "XOM", "CVX",
    # 金融与传统巨头
    "JPM", "V", "MA", "BRK.B", "GE", "RTX", "LMT", "WM",
    # 大宗商品
    "NEM", "FCX", "GLD", "IAU"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 大龙虾2.0 - %(message)s', datefmt='%H:%M:%S')
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
输出必须是纯粹的 JSON 格式，不要输出任何Markdown标记：

{{
  "emergency_halt": false,
  "macro_sentiment": 0.0,
  "sector_sentiment": {{
    "XLK": 0.0, "XLE": 0.0, "GLD": 0.0, "XLF": 0.0, "XLU": 0.0
  }},
  "stock_sentiment": {{
     // 务必从以下名单中挑选受严重影响的个股打分(-1.0到1.0)：
     // {', '.join(STOCKS)}
  }}
}}

【最新全球新闻】：
{news_text}
"""
    try:
        api_key_to_use = OPENAI_API_KEY if "sk-" in OPENAI_API_KEY else os.environ.get("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key_to_use)
        
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
        
        # 清理多余的 Markdown 标记，防止 JSON 解析崩溃
        if result_text.startswith("```json"): 
            result_text = result_text[7:]
        elif result_text.startswith("```"):
            result_text = result_text[3:]
            
        if result_text.endswith("```"): 
            result_text = result_text[:-3]
            
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"❌ GPT-4 调用失败: {e}")
        return None

# ================= ⚙️ 原始 Web 框架核心 =================
app = Flask(__name__)

# 全局内存情报
latest_intel = {
    "emergency_halt": False,
    "macro_sentiment": 0.0,
    "sector_sentiment": {},
    "stock_sentiment": {},
    "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    "status": "Initializing..."
}

def background_task():
    """保留了您上午正常运行的后台定时刷新机制"""
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
                    logger.info("✅ 情报已更新")
        except Exception as e:
            logger.error(f"刷新异常: {e}")
        time.sleep(FETCH_INTERVAL_MINUTES * 60)

@app.route('/')
def get_intel():
    """保留了您上午正常运行的 Web 接口"""
    return jsonify(latest_intel)

if __name__ == "__main__":
    # 启动后台线程
    t = threading.Thread(target=background_task, daemon=True)
    t.start()
    
    # 启动 Flask Web 服务器
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)