import os
import sys
import requests
import telebot
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from tavily import TavilyClient

# ... [保留原本的啟動日誌與 fetch_realtime_news 不變] ...

@tool("X (Twitter) Trend Fetcher")
def fetch_x_tweets(query: str) -> str:
    """必須使用此工具抓取 X (Twitter) 上最新的市場趨勢推文。"""
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token: return "X API 未設定"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    
    # 修正 Bug：使用 params 自動處理 URL 編碼，避免 query 中有空白導致 400 錯誤
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": f"{query} -is:retweet",
        "tweet.fields": "created_at,author_id",
        "max_results": 10
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if "data" not in data: return "無相關推文"
        tweets = ["【社群聲音】"]
        for t in data["data"][:3]: # 物理限制 3 則
            tweets.append(f"時間: {t['created_at']}\n內容: {t['text']}\n---")
        return "\n".join(tweets)
    except Exception as e:
        return f"推文抓取失敗: {str(e)}"

# ==========================================
# 🧠 第二部分：喚醒四大天王 LLM (滿血回歸版)
# ==========================================
print("🧠 [系統] 正在連接四核 AI 引擎 (2026 旗艦陣容)...")
sys.stdout.flush()

llm_grok = LLM(
    model="openai/grok-4-1-fast-reasoning", 
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)
llm_gpt = LLM(
    model="gpt-5.2-pro-2025-12-11", 
    api_key=os.getenv("OPENAI_API_KEY")
)
llm_claude = LLM(
    model="openrouter/anthropic/claude-sonnet-4.6", 
    api_key=os.getenv("OPENROUTER_API_KEY")
)
llm_gemini = LLM(
    model="gemini/gemini-3.1-pro-preview", 
    api_key=os.getenv("GEMINI_API_KEY")
)

# ==========================================
# 🤖 第三部分：配置四位 Agent 與對應任務
# ==========================================

# 1. Grok: 幣圈偵察
agent_crypto = Agent(
    role='幣圈與宏觀偵察員',
    goal='掃描加密貨幣動態與社群 FOMO/FUD 情緒',
    backstory='你對流動性極度敏銳，必須嚴格使用工具抓取新聞與推文，絕不捏造數據。',
    tools=[fetch_realtime_news, fetch_x_tweets],
    llm=llm_grok,
    verbose=True
)
task_crypto = Task(
    description='使用 News Fetcher 抓取 5 則 Crypto 新聞，並用 X Fetcher 抓取 3 則市場推文，整理出目前的資金情緒。',
    expected_output='幣圈現況與 X 社群情緒分析報告。',
    agent=agent_crypto
)

# 2. GPT: 科技研究
agent_tech = Agent(
    role='前沿科技研究員',
    goal='追蹤全球最新 AI 模型、算力經濟學與太空/核能發展',
    backstory='你是頂尖科技分析師，負責提供客觀的科技產業動態。',
    tools=[fetch_realtime_news],
    llm=llm_gpt,
    verbose=True
)
task_tech = Task(
    description='搜尋關於 AI 算力、核能或太空科技的最新市場動態，產出摘要。',
    expected_output='科技與 AI 算力市場情報。',
    agent=agent_tech
)

# 3. Claude: 首席風控
agent_risk = Agent(
    role='首席風險風控官',
    goal='揭露市場炒作與清算風險，提供毒舌批判',
    backstory='你是華爾街最嚴格的風控經理。你有一個絕對的鐵律：【絕對不碰、不提任何台灣股市標的】，你的報告中不允許出現任何關於台股的建議。你擅長戳破泡沫。',
    llm=llm_claude,
    verbose=True
)
task_risk = Task(
    description='審視前兩位研究員的報告，給出毒舌的風險提示。再次確認你的報告中絕對沒有提及台灣股票。',
    expected_output='冷靜且毒舌的市場風險審計報告。',
    agent=agent_risk
)

# 4. Gemini: 機構主編
agent_editor = Agent(
    role='機構主編',
    goal='將所有報告彙整為結構清晰的最終戰報',
    backstory='你是財經媒體主編，負責最終排版，讓大忙人一眼看懂重點。',
    llm=llm_gemini,
    verbose=True
)
task_editor = Task(
    description='整合幣圈情緒、科技情報與風控報告，排版成易讀的 Telegram 戰報格式 (使用適當的 emoji)。',
    expected_output='最終可直接發布的完整日報。',
    agent=agent_editor
)

# ==========================================
# 🚀 第四部分：啟動系統與發送 Telegram
# ==========================================
print("🔥 [系統] 四核引擎已就緒，開始執行任務！")
sys.stdout.flush()

q_silicon_crew = Crew(
    agents=[agent_crypto, agent_tech, agent_risk, agent_editor],
    tasks=[task_crypto, task_tech, task_risk, task_editor],
    process=Process.sequential,
    verbose=True
)

try:
    # 這裡啟動整個分析流程
    final_report = q_silicon_crew.kickoff()
    
    print("✅ [系統] 分析完畢，準備發送 Telegram...")
    sys.stdout.flush()
    
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        # 截斷保護機制
        report_text = str(final_report)
        if len(report_text) > 4000:
            report_text = report_text[:4000] + "\n\n...(字數超出限制，已自動截斷)"
            
        bot.send_message(TELEGRAM_CHAT_ID, report_text)
        print("📩 [系統] Telegram 報告發送成功！")
    else:
        print("❌ [錯誤] 找不到 Telegram 金鑰，無法發送。")
        
except Exception as e:
    print(f"❌ [系統崩潰] 執行時發生錯誤: {e}")

print("🏁 [系統] 正常結束，下班。")
sys.stdout.flush()
