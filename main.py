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

# 🎯 监控标的池 
STOCKS = [
    "NVDA", "AMD", "AVGO", "TSM", "ARM", "MSFT", "GOOGL", "META", "AMZN", "PLTR",
    "AAPL", "NFLX", "ADBE", "MU", "INTC", "QCOM", "TSLA",
    "MSTR", "COIN", "IBIT", "LLY", "NVO",
    "VST", "CEG", "NRG", "GEV", "CAT", "WMT", "COST", "XOM", "CVX",
    "JPM", "V", "MA", "BRK.B", "GE", "RTX", "LMT", "WM",
    "NEM", "FCX", "GLD", "IAU"
]

# 核心驱动标的：只抽取前5个最能代表当前行情的股票获取专属新闻
CORE_NEWS_TICKERS = ["NVDA", "TSLA", "MSTR", "AAPL", "MSFT"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 大龙虾3.3 (全副武装版) - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger()

# ================= 📡 Finnhub 纯净数据雷达 (带浏览器伪装) =================
def fetch_finnhub_news():
    """军工级防弹版抓取引擎，带浏览器伪装和X光级报错诊断"""
    headlines = []
    
    # 暴力清洗密钥中的空格和换行符，防止破坏 URL 结构
    raw_key = os.environ.get("FINNHUB_API_KEY")
    if not raw_key:
        logger.error("🚨 致命错误：系统环境变量中找不到 FINNHUB_API_KEY！请检查 Railway 设置。")
        return headlines
        
    clean_key = raw_key.replace(" ", "").replace("\n", "").strip()
    
    # 核心绝杀：伪装成真实的 Windows Chrome 浏览器，穿透反爬虫防火墙
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 1. 抓取大盘新闻
    try:
        url_general = f"https://finnhub.io/api/v1/news?category=general&token={clean_key}"
        res = requests.get(url_general, headers=headers, timeout=15)
        
        if res.status_code == 200:
            try:
                news_data = res.json()
                if isinstance(news_data, list) and len(news_data) > 0:
                    headlines.append("【全球宏观与大盘新闻】")
                    for entry in news_data[:6]:
                        if isinstance(entry, dict):
                            headline = str(entry.get('headline') or "无标题").strip()
                            summary = str(entry.get('summary') or "").strip()
                            headlines.append(f"- {headline}: {summary[:150]}")
            except Exception as e:
                logger.error(f"⚠️ 宏观新闻 JSON 解析失败。API返回内容: {res.text[:200]}")
        else:
            # X光透视：如果不是200，精确打印状态码和 Finnhub 返回的拒绝理由
            logger.error(f"❌ 宏观新闻请求被服务器拒绝！状态码: {res.status_code}, 理由: {res.text[:200]}")
            
    except Exception as e:
        # 捕捉底层的网络断开、DNS 解析失败等严重异常
        logger.error(f"❌ 宏观新闻发生底层网络断连: {type(e).__name__} - {str(e)}")

    # 2. 抓取个股新闻
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    for ticker in CORE_NEWS_TICKERS:
        try:
            url_ticker = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={yesterday}&to={today}&token={clean_key}"
            res = requests.get(url_ticker, headers=headers, timeout=10)
            
            if res.status_code == 200:
                try:
                    news_data = res.json()
                    if isinstance(news_data, list) and len(news_data) > 0:
                        headlines.append(f"\n【{ticker} 专属突发新闻】")
                        for entry in news_data[:3]:
                            if isinstance(entry, dict):
                                headline = str(entry.get('headline') or "无标题").strip()
                                summary = str(entry.get('summary') or "").strip()
                                headlines.append(f"- {headline}: {summary[:100]}")
                except Exception:
                    logger.error(f"⚠️ {ticker} JSON 解析失败。返回内容: {res.text[:200]}")
            else:
                logger.error(f"❌ 抓取 {ticker} 被拒绝！状态码: {res.status_code}, 理由: {res.text[:200]}")
                
        except Exception as e:
            logger.error(f"❌ 抓取 {ticker} 发生网络断连: {type(e).__name__} - {str(e)}")
            
    return headlines

# ================= 🧠 GPT-4o 宏观推演引擎 =================
def call_gpt4_financial_brain(news_text):
    if not OPENAI_API_KEY:
        logger.error("🚨 致命错误：未配置 OPENAI_API_KEY！")
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
        client = OpenAI(api_key=OPENAI_API_KEY.strip())
        response = client.chat.completions.create(
            model=MODEL_NAME,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a professional Wall Street algorithmic trading AI. You must output strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        
        result_text = response.choices[0].message.content.strip()
        
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
            else:
                logger.warning("⚠️ 本次轮询未获取到任何新闻，AI 推演已跳过。")
        except Exception as e:
            logger.error(f"后台刷新异常: {e}")
            
        time.sleep(FETCH_INTERVAL_MINUTES * 60)

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=background_worker, daemon=True)
    t.start()

@app.get('/')
def get_intel():
    return latest_intel

@app.get('/{catchall:path}')
def get_intel_catchall(catchall: str):
    return latest_intel

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host='0.0.0.0', port=port)