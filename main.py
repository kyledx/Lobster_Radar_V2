import os
import time
from fastapi import FastAPI
import uvicorn

app = FastAPI()

current_sentiment = {
    "timestamp": "2023-10-25 09:45:00",
    "macro_sentiment": 0.0,
    "sector_sentiment": {"XLK": 0.0, "XLE": 0.0, "GLD": 0.0},
    "stock_sentiment": {"NVDA": 0.0, "CEG": 0.0},
    "emergency_halt": False
}

@app.get("/")
def read_root():
    return {"status": "Lobster Radar is Online. Go to /sentiment"}

@app.get("/sentiment")
def get_sentiment():
    current_sentiment["timestamp"] = time.strftime('%Y-%m-%d %H:%M:%S')
    return current_sentiment

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)