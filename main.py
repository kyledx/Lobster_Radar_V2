import os
import json
import time
import requests
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from openai import OpenAI

app = FastAPI()

# ==========================================
# 🔧 云端核心配置区
# ==========================================
# ⚠️ 请确保在 Railway 的 Variables 中配置了这两个 Key
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# 监控池 (为了云端速度，我们精简提取最具代表性的风向标)
TARGET_TICKERS = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL"]

def fetch_finnhub_news(ticker: str):
    """从 Finnhub 拉取过去 24 小时的最新一条新闻"""
    if not FINNHUB_API_KEY:
        return None
    
    # 获取今天和昨天的时间戳 (格式 YYYY-MM-DD)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={today}&to={today}&token={FINNHUB_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        news_data = response.json()
        if news_data and len(news_data) > 0:
            return news_data[0]['headline'] # 只取最新的一条头条
    except Exception as e:
        print(f"Finnhub 拉取失败: {e}")
    return None

def analyze_with_openai(ticker: str, headline: str):
    """调用 OpenAI 进行情绪打分"""
    if not OPENAI_API_KEY:
        return {"sentiment_score": 0.0, "emergency_halt": False}
        
    client = OpenAI(api_key=OPENAI_API_KEY)
    system_prompt = """
    你是一个华尔街量化大脑。评估突发新闻对标的资产的价格冲击。
    重点评估大盘ETF(SPY/QQQ)对整个市场的系统性影响。
    必须输出如下 JSON 格式：
    {
        "sentiment_score": 浮点数 (-1.0代表极度利空, 1.0代表极度利好, 0代表噪音),
        "emergency_halt": true 或 false
    }
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"标的: {ticker}\n最新突发新闻: {headline}"}
            ],
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception:
        return {"sentiment_score": 0.0, "emergency_halt": False}

@app.get("/")
def root_health_check():
    """根目录探针：用于 Railway 检查服务是否存活"""
    return {"status": "Lobster Cloud Radar is ALIVE 🦞"}

@app.get("/fetch_sentiment")
def get_market_sentiment():
    """核心接口：本地信使呼叫此接口获取最新情报"""
    if not FINNHUB_API_KEY or not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Cloud API Keys are missing!")

    # 初始化 V40.35 标准信箱格式
    intel_report = {
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        "macro_sentiment": 0.0,
        "emergency_halt": False,
        "sector_sentiment": {},
        "stock_sentiment": {}
    }

    print("☁️ [云端大龙虾] 收到本地请求，开始执行 Finnhub+OpenAI 联合推演...")
    
    for ticker in TARGET_TICKERS:
        headline = fetch_finnhub_news(ticker)
        if not headline:
            continue
            
        ai_result = analyze_with_openai(ticker, headline)
        score = ai_result.get("sentiment_score", 0.0)
        halt = ai_result.get("emergency_halt", False)
        
        # 归类写入
        if ticker in ["SPY", "QQQ"]:
            # 如果存在多条宏观数据，取平均值或极端值，这里简单处理为覆盖
            intel_report["macro_sentiment"] = score 
        else:
            intel_report["stock_sentiment"][ticker] = score
            
        if halt:
            intel_report["emergency_halt"] = True
            
        # 避免触发 Finnhub 免费版每秒并发限制
        time.sleep(1) 

    print("☁️ [云端大龙虾] 推演完成，正在将情报下发至本地...")
    return intel_report