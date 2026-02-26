import os
import requests
import telebot
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from tavily import TavilyClient

# ==========================================
# 🛡️ 第一部分：強勢過濾自訂工具區
# ==========================================

@tool("Real-Time News Fetcher")
def fetch_realtime_news(query: str) -> str:
    """必須使用此工具抓取最新的財經與加密貨幣新聞。強制回傳過去 24 小時內的 5 則新聞。"""
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = client.search(
            query=query,
            topic="news",      # 強制進入新聞模式
            days=1,            # 鎖定 24 小時內
            max_results=5      # 物理限制 5 則
        )
        
        results = ["【最新 5 則重要新聞】"]
        for idx, item in enumerate(response.get("results", [])):
            results.append(f"{idx+1}. 標題: {item['title']}\n連結: {item['url']}\n摘要: {item['content']}")
        return "\n\n".join(results)
    except Exception as e:
        return f"新聞抓取失敗: {str(e)}"


@tool("X (Twitter) Trend Fetcher")
def fetch_x_tweets(query: str) -> str:
    """必須使用此工具抓取 X (Twitter) 上最新的市場趨勢推文。"""
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token:
        return "X_BEARER_TOKEN 未設定，無法抓取推文。"
    
    headers = {"Authorization": f"Bearer {bearer_token}"}
    # 使用 X API v2 搜尋最近的推文，過濾掉轉推 (retweets)
    url = f"https://api.twitter.com/2/tweets/search/recent?query={query} -is:retweet&tweet.fields=created_at,author_id&max_results=10"
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if "data" not in data:
            return "目前沒有找到相關推文，或 X API 達到限制。"
            
        tweets = ["【X (Twitter) 最新市場聲音】"]
        for t in data["data"][:3]:  # 物理限制：只取最精華的 3 則
            tweets.append(f"推文時間: {t['created_at']}\n內容: {t['text']}\n---")
        return "\n".join(tweets)
    except Exception as e:
        return f"X 推文抓取失敗: {str(e)}"


# ==========================================
# 🤖 第二部分：為 Agent 裝備新武器
# ==========================================

# (請找到你原本定義 researcher 的地方，把 tools 換成上面這兩個)
researcher = Agent(
    role='首席加密與總經研究員',
    goal='精準抓取最新 5 則市場新聞，並從 X 上聆聽市場情緒',
    backstory='你是一個不容許過期資訊的頂級分析師。你必須嚴格使用 "Real-Time News Fetcher" 與 "X Trend Fetcher" 來獲取數據，絕對不允許自己捏造新聞或憑空想像推文。',
    tools=[fetch_realtime_news, fetch_x_tweets], # <== 把兩個新工具交給它
    # llm=你的模型設定 (保留你原本的寫法)
    verbose=True
)

# (在 Task 的部分，記得加上強勢的指令)
research_task = Task(
    description='''
    1. 使用 "Real-Time News Fetcher" 搜尋當前市場最重要的 5 則新聞 (關鍵字可使用 "Crypto OR Macro economy")。
    2. 使用 "X Trend Fetcher" 搜尋目前推特上的市場情緒 (關鍵字可使用 "BTC OR Crypto")。
    3. 將上述兩者的真實資料彙整，不准遺漏，也不准捏造。
    ''',
    expected_output='包含 5 則真實新聞摘要與 3 則 X 推文的市場情報整理。',
    agent=researcher
)
