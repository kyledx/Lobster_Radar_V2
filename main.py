import os
import json
import time
import logging
from datetime import datetime, timezone
import feedparser
from openai import OpenAI

# ================= 🔧 云端系统配置 =================
# 🛡️ 军用级安全：从 GitHub Secrets 环境变量中动态读取 API KEY，绝不明文暴露！
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 强制防呆检测：如果没有读到 Key，直接拉响警报并停止运行
if not OPENAI_API_KEY:
    raise ValueError("🚨 致命错误：找不到 OPENAI_API_KEY！请检查 GitHub Secrets 是否配置正确！")

MODEL_NAME = "gpt-4o"  # 使用 GPT-4o 获取顶级逻辑推理能力

# 📡 全球宏观雷达阵列 (RSS Feeds)
RSS_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # CNBC 财经
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", # 华尔街日报 市场
    "https://www.investing.com/rss/news_25.rss", # Investing 宏观
    "https://www.investing.com/rss/commodities.rss", # 大宗商品 (原油/黄金)
    "https://finance.yahoo.com/news/rssindex" # 雅虎财经
]

# 🎯 监控标的池 (与 V29.86 战车对齐)
SECTORS = ["XLK", "XLE", "XLF", "GLD", "XLU", "XLC", "XLY"]
STOCKS = [
    "NVDA", "AAPL", "MSFT", "AMD", "AVGO", "TSM", "META", "GOOGL", "AMZN",
    "XOM", "CVX", "CEG", "VST", "NRG",
    "JPM", "V", "MA",
    "NEM", "FCX", "MSTR", "COIN", "LLY"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 大龙虾2.0(云端版) - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger()

client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_global_news():
    """📡 扫描全球新闻主干道，提取核心头条"""
    logger.info("📡 雷达天线展开，正在扫描全球宏观新闻...")
    headlines = []
    
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            # 每个源只取最新的 5 条核心新闻，防止 Token 爆炸
            for entry in feed.entries[:5]:
                headlines.append(f"- {entry.title}: {entry.get('summary', '')[:200]}")
        except Exception as e:
            logger.error(f"⚠️ 雷达源读取失败 {url}: {e}")
            
    return headlines

def call_gpt4_financial_brain(news_text):
    """🧠 召唤 GPT-4 华尔街首席宏观分析师进行逻辑推演"""
    
    prompt = f"""
你现在是华尔街最顶尖的宏观对冲基金经理兼量化策略师。
我将为你提供过去几小时内美股和全球宏观的最新新闻头条。
你需要深刻理解“资金轮动、地缘政治博弈、美元指数潮汐、跨资产传导”等高级金融逻辑。

【核心常识纠正】：
1. 战争/地缘冲突 绝对不等于“世界末日”。它通常对能源(XLE, XOM)是极大利好，对国防军工是利好。
2. 战争不一定利好黄金。如果战争引发通胀预期，导致美联储加息预期升温，强势美元反而会镇压黄金(GLD)下跌。
3. 科技股(XLK)可能因为供应链危机或高利率承压，此时资金会流入避风港(公用事业XLU、能源XLE)。

【任务要求】：
阅读以下新闻，推演对具体板块和个股的情绪影响。
输出必须是纯粹的 JSON 格式，严格包含以下结构，不要输出任何额外的解释或Markdown标记（如 ```json 等）：

{{
  "emergency_halt": false,  // 只有发生爆发第三次世界大战、美股熔断、美国债务违约等绝对毁灭性事件时才给 true。普通冲突、加息、暴跌一律给 false！
  "macro_sentiment": 0.0,   // 大盘整体情绪，范围 -1.0 到 1.0
  "sector_sentiment": {{
    "XLK": 0.0, "XLE": 0.0, "GLD": 0.0, "XLF": 0.0, "XLU": 0.0
  }}, // 范围 -1.0 到 1.0。重点区分避风港和承压板块。
  "stock_sentiment": {{
    // 在这里列出受新闻强烈影响的个股，范围 -1.0 到 1.0。中性(0.0)的可以不写。
    // 备选池: {', '.join(STOCKS)}
  }}
}}

【最新全球新闻】：
{news_text}
"""
    
    try:
        logger.info("🧠 正在将全球情报注入 GPT-4 宏观引擎进行降维推演...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a professional Wall Street algorithmic trading AI. You output strict, valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2, # 保持低温度，确保逻辑严谨和 JSON 格式稳定
            max_tokens=1000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # 清理可能附带的 Markdown 标记
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        sentiment_data = json.loads(result_text)
        return sentiment_data
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ GPT-4 输出的 JSON 格式损坏: {e}\n输出内容: {result_text}")
        return None
    except Exception as e:
        logger.error(f"❌ GPT-4 大脑调用失败: {e}")
        return None

def main():
    logger.info("🦞 大龙虾 2.0 (全视之眼 GPT-4 云端部署版) 已启动！监听全球主干道...")
    
    try:
        # 1. 抓取全球新闻
        headlines = fetch_global_news()
        
        if not headlines:
            logger.warning("⚠️ 未抓取到任何新闻，流程结束。")
            return
            
        news_text = "\n".join(headlines)
        
        # 2. 召唤 GPT-4 脑核心计算情绪
        sentiment_data = call_gpt4_financial_brain(news_text)
        
        if sentiment_data:
            # 3. 压入时间戳 (V29.86 防呆机制需要此时间戳验证数据新鲜度)
            sentiment_data['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            
            # 4. 写入指令文件给战车 (供 GitHub Actions 提交到仓库)
            with open('news_sentiment.json', 'w', encoding='utf-8') as f:
                json.dump(sentiment_data, f, indent=4, ensure_ascii=False)
            
            # --- 日志汇报 ---
            halt_msg = "🚨核弹预警🚨" if sentiment_data.get('emergency_halt') else "🟢安全"
            macro_score = sentiment_data.get('macro_sentiment', 0.0)
            logger.info(f"✅ 情报降维完成 | 状态: {halt_msg} | 宏观情绪: {macro_score:.2f}")
            logger.info(f"板块分化: {sentiment_data.get('sector_sentiment', {})}")
            
            stocks = sentiment_data.get('stock_sentiment', {})
            hot_stocks = {k: v for k, v in stocks.items() if abs(v) >= 0.3}
            if hot_stocks:
                logger.info(f"🔥 狙击目标锁定: {hot_stocks}")
            else:
                logger.info("❄️ 当前无极端异动个股。")
                
        else:
            logger.warning("⚠️ 本轮情报解析失败。")
            
    except Exception as e:
        logger.error(f"🚨 主程序异常: {e}")

if __name__ == "__main__":
    main()