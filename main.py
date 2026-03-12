import os
import json
import time
import requests
import uvicorn
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from openai import OpenAI

app = FastAPI()

# ==========================================
# 🔧 云端核心配置区
# ==========================================
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# 监控池 (核心风向标)
TARGET_TICKERS = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL"]

def fetch_finnhub_news(ticker: str):
    if not FINNHUB_API_KEY:
        return None
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={today}&to={today}&token={FINNHUB_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        news_data = response.json()
        if news_data and len(news_data) > 0:
            return news_data[0]['headline']
    except Exception as e:
        print(f"Finnhub 拉取失败: {e}")
    return None

def analyze_with_openai(ticker: str, headline: str):
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
    return {"status": "Lobster Cloud Radar is ALIVE 🦞"}

@app.get("/fetch_sentiment")
def get_market_sentiment():
    if not FINNHUB_API_KEY or not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Cloud API Keys are missing!")

    intel_report = {
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        "macro_sentiment": 0.0,
        "emergency_halt": False,
        "sector_sentiment": {},
        "stock_sentiment": {}
    }

    print("☁️ [云端大龙虾] 开始执行 Finnhub+OpenAI 联合推演...")
    
    for ticker in TARGET_TICKERS:
        headline = fetch_finnhub_news(ticker)
        if not headline:
            continue
            
        ai_result = analyze_with_openai(ticker, headline)
        score = ai_result.get("sentiment_score", 0.0)
        halt = ai_result.get("emergency_halt", False)
        
        if ticker in ["SPY", "QQQ"]:
            intel_report["macro_sentiment"] = score 
        else:
            intel_report["stock_sentiment"][ticker] = score
            
        if halt:
            intel_report["emergency_halt"] = True
            
        time.sleep(1) 

    print("☁️ [云端大龙虾] 推演完成！")
    return intel_report

# ==========================================
# 🚀 极其关键：强行撑开出菜口，对接 Railway 动态端口
# ==========================================
if __name__ == "__main__":
    # Railway 每次部署都会随机分配一个端口，必须动态获取！
    port = int(os.environ.get("PORT", 8000))
    # host 必须是 0.0.0.0，允许所有外部网络敲门
    uvicorn.run(app, host="0.0.0.0", port=port)