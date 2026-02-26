import os
import sys
import requests
import telebot
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from tavily import TavilyClient

# ==========================================
# 🔍 啟動日誌與防呆檢查
# ==========================================
print("🚀 [系統] 程式開始執行...")
print(f"Python 執行路徑: {sys.executable}")
print("--- 檢查環境變數 ---")
print(f"TELEGRAM_BOT_TOKEN: {'✅ 成功載入' if os.getenv('TELEGRAM_BOT_TOKEN') else '❌ 未設定'}")
print(f"TELEGRAM_CHAT_ID: {'✅ 成功載入' if os.getenv('TELEGRAM_CHAT_ID') else '❌ 未設定'}")
print(f"TAVILY_API_KEY: {'✅ 成功載入' if os.getenv('TAVILY_API_KEY') else '❌ 未設定'}")
print(f"X_BEARER_TOKEN: {'✅ 成功載入' if os.getenv('X_BEARER_TOKEN') else '❌ 未設定'}")
print("--------------------")
sys.stdout.flush()  # 強制將日誌推送到 GCP

# ==========================================
# 🛡️ 第一部分：強勢過濾自訂工具區
# ==========================================
@tool("Real-Time News Fetcher")
def fetch_realtime_news(query: str) -> str:
    """必須使用此工具抓取最新的財經與加密貨幣新聞。強制回傳過去 24 小時內的 5 則新聞。"""
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "TAVILY_API_KEY 未設定，無法抓取新聞。"
            
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query, topic="news", days=1, max_results=5
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
    url = f"https://api.twitter.com/2/tweets/search/recent?query={query} -is:retweet&tweet.fields=created_at,author_id&max_results=10"
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if "data" not in data:
            return "目前沒有找到相關推文，或 X API 達到限制。"
            
        tweets = ["【X (Twitter) 最新市場聲音】"]
        for t in data["data"][:3]:
            tweets.append(f"推文時間: {t['created_at']}\n內容: {t['text']}\n---")
        return "\n".join(tweets)
    except Exception as e:
        return f"X 推文抓取失敗: {str(e)}"


# ==========================================
# 🤖 第二部分：定義 Agent 與 Task
# ==========================================
print("🤖 [系統] 正在初始化 Agent 與 Task...")
sys.stdout.flush()

researcher = Agent(
    role='首席加密與總經研究員',
    goal='精準抓取最新 5 則市場新聞，並從 X 上聆聽市場情緒',
    backstory='你是一個不容許過期資訊的頂級分析師。你必須嚴格使用 "Real-Time News Fetcher" 與 "X Trend Fetcher" 來獲取數據，絕對不允許自己捏造新聞或憑空想像推文。',
    tools=[fetch_realtime_news, fetch_x_tweets],
    verbose=True
    # 註：如果沒有特別寫 llm=... ，CrewAI 預設會去抓環境變數裡的 OPENAI_API_KEY
)

research_task = Task(
    description='''
    1. 使用 "Real-Time News Fetcher" 搜尋當前市場最重要的 5 則新聞 (關鍵字可使用 "Crypto OR Macro economy")。
    2. 使用 "X Trend Fetcher" 搜尋目前推特上的市場情緒 (關鍵字可使用 "BTC OR Crypto")。
    3. 將上述兩者的真實資料彙整，不准遺漏，也不准捏造，並加上你的專業見解。
    ''',
    expected_output='包含 5 則真實新聞摘要與 3 則 X 推文的市場情報整理。',
    agent=researcher
)


# ==========================================
# 🚀 第三部分：啟動任務與發送 Telegram
# ==========================================
print("🧠 [系統] 開始組建 Crew 並啟動思考引擎...")
sys.stdout.flush()

my_crew = Crew(
    agents=[researcher],
    tasks=[research_task],
    process=Process.sequential,
    verbose=True
)

try:
    # 這裡才是真正開始搜尋與寫作的按鈕！
    result = my_crew.kickoff()
    
    print("✅ [系統] Crew 執行完畢，準備發送 Telegram...")
    sys.stdout.flush()
    
    # 發送 Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        
        # 安全機制：Telegram 訊息長度上限為 4096，超過會報錯
        final_report = str(result)
        if len(final_report) > 4000:
            final_report = final_report[:4000] + "\n\n...(字數超出限制，已自動截斷)"
            
        bot.send_message(TELEGRAM_CHAT_ID, final_report)
        print("📩 [系統] Telegram 報告發送成功！")
    else:
        print("❌ [錯誤] 找不到 TELEGRAM 金鑰，報告已產出但無法發送！")
        print(f"報告內容：\n{result}")
        
except Exception as e:
    print(f"❌ [系統崩潰] 程式執行時發生嚴重錯誤: {e}")

print("🏁 [系統] 程式正常結束。")
sys.stdout.flush()
