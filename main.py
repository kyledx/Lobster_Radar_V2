import os
import json
import logging
import time
import threading
import requests
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from fastapi import FastAPI
import uvicorn

# ================= 🔧 核心配置区 =================
# 🛡️ 军用级安全：从 Railway 环境变量读取双密钥
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY") 

MODEL_NAME = "gpt-4o"  
FETCH_INTERVAL_MINUTES = 15  

# 🎯 监控标的池 (已与 V29 战车 100% 对齐)
STOCKS = [
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MSFT", "GOOGL", "META", "AMZN", "PLTR",
    "AAPL", "NFLX", "ADBE", "MU", "INTC", "QCOM", "TSLA",
    "MSTR", "COIN", "IBIT", "LLY", "NVO",
    "VST", "CEG", "NRG", "GEV", "CAT", "WMT", "COST", "XOM", "CVX",
    "JPM", "V", "MA", "BRK.B", "GE", "RTX", "LMT", "WM",
    "NEM", "FCX", "GLD", "IAU"
]

# 核心驱动标的：只抽取前5个最能代表当前行情的股票获取专属新闻，避免 Token 爆炸
CORE_NEWS_TICKERS = ["NVDA", "TSLA", "MSTR", "AAPL", "MSFT"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 大龙虾3.1 (军工防弹版) - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger()

# ================= 📡 Finnhub 纯净数据雷达 =================
def fetch_finnhub_news():
    """彻底替换 RSS，使用 Finnhub 抓取结构化金融新闻，加入极度严格的防崩处理"""
    headlines = []
    if not FINNHUB_API_KEY:
        logger.error("🚨 警告：未配置 FINNHUB_API_KEY！无法抓取实时金融新闻。")
        return headlines

    # 1. 抓取全市场宏观新闻 (General Market News)
    try:
        url_general = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        res = requests.get(url_general, timeout=10)
        if res.status_code == 200:
            news_data = res.json()
            
            # 【深度纠正 1】：必须判断数据类型是否为 List，防范 API 限流时返回 {"error": "..."} 导致字典切片崩溃
            if isinstance(news_data, list):
                headlines.append("【全球宏观与大盘新闻】")
                for entry in news_data[:6]: 
                    # 【深度纠正 2】：彻底防范 Finnhub 返回 null 导致的 NoneType 连环崩溃
                    headline = entry.get('headline') or "无标题"
                    summary = entry.get('summary') or ""
                    headlines.append(f"- {headline}: {summary[:150]}")
            else:
                logger.error(f"⚠️ Finnhub宏观接口返回了非预期的格式 (非列表): {news_data}")
    except Exception as e:
        logger.error(f"❌ Finnhub宏观新闻获取失败: {e}")

    # 2. 抓取核心风向标个股新闻 (Company Specific News)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    for ticker in CORE_NEWS_TICKERS:
        try:
            url_ticker = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={yesterday}&to={today}&token={FINNHUB_API_KEY}"
            res = requests.get(url_ticker, timeout=5)
            if res.status_code == 200:
                news_data = res.json()
                
                # 同样执行严格的数据类型和空值校验
                if isinstance(news_data, list) and len(news_data) > 0:
                    headlines.append(f"\n【{ticker} 专属突发新闻】")
                    for entry in news_data[:3]: 
                        headline = entry.get('headline') or "无标题"
                        summary = entry.get('summary') or ""
                        headlines.append(f"- {headline}: {summary[:100]}")
        except Exception as e:
            logger.error(f"❌ 抓取 {ticker} 个股新闻失败: {e}")
            continue

    return headlines

# ================= 🧠 GPT-4o 宏观推演引擎 =================
def call_gpt4_financial_brain(news_text):
    if not OPENAI_API_KEY:
        logger.error("🚨 致命错误：未配置 OPENAI_API_KEY！请在 Railway 控制台 Variables 中添加。")
        return None

    if not news_text:
        logger.warning("⚠️ 没有抓取到任何新闻，跳过本次 AI 推演。")
        return None

    prompt = f"""你现在是华尔街最顶尖的宏观对冲基金经理兼量化策略师。
我将为你提供过去几小时内，由 Finnhub 抓取的最新纯净美股和全球宏观新闻。
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

【最新 Finnhub 全球新闻情报】：
{news_text}
"""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a professional Wall Street algorithmic trading AI. You must output strictly valid JSON based on Finnhub news data."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # 【深度纠正 3】：暴力清洗 OpenAI 可能夹带的 Markdown 代码块标记，彻底杜绝 json.loads 报错
        if result_text.startswith("```"):
            result_text = result_text.strip("`").replace("json\n", "", 1).strip()
            
        return json.loads(result_text)
            
    except Exception as e:
        logger.error(f"❌ GPT-4o 调用或 JSON 解析失败: {e}")
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
    """云端死循环线程：定时抓 Finnhub 新闻 -> GPT-4o 算分 -> 存入内存"""
    global latest_intel
    logger.info("🚀 Finnhub + GPT-4o 脑核心后台线程已点火...")
    while True:
        try:
            headlines = fetch_finnhub_news()
            if headlines:
                news_text = "\n".join(headlines)
                logger.info("✅ 成功抓取 Finnhub 结构化新闻，正在交由 AI 推演...")
                
                data = call_gpt4_financial_brain(news_text)
                if data:
                    data['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    data['status'] = "Online - Finnhub & GPT-4o Engine Active"
                    latest_intel = data
                    logger.info("🎯 宏观情绪 JSON 已成功生成并更新至 Web 端！")
        except Exception as e:
            logger.error(f"后台刷新异常: {e}")
            
        # 严格遵守轮询间隔，防止烧钱
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
@app.get('/{catchall:path}')
def get_intel_catchall(catchall: str):
    return latest_intel

if __name__ == "__main__":
    # 保留给本地测试的入口，Railway 将使用 Procfile 启动
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host='0.0.0.0', port=port)