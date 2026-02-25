import os
import requests
import telebot
import logging
from urllib.parse import quote
from textwrap import dedent
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# 載入本地端 .env 變數 (雲端部署時會自動覆蓋)
load_dotenv()

# 設定基礎日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# 一、 外部 API 工具定義 (Tools)
# ==========================================

@tool("Tavily Market Search")
def market_search_tool(query: str) -> str:
    """搜尋全球宏觀、數位資產與『AI科技』即時新聞。"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key: return "System Error: TAVILY_API_KEY not found."
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, search_depth="advanced", max_results=5, topic="news", days=1)
        return str(response.get("results", "No results found."))
    except Exception as e: return f"Tavily Failed: {str(e)}"

@tool("X Real-time Trend Search")
def x_search_tool(query: str) -> str:
    """搜尋 X (Twitter) 上最新的討論情緒與科技圈發文。"""
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token: return "System Error: X_BEARER_TOKEN not found."
    # 加入 quote() 進行 URL 編碼，防止中文或空格導致 API 崩潰
    url = f"https://api.twitter.com/2/tweets/search/recent?query={quote(query)}&max_results=10"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            tweets = response.json().get("data", [])
            return "\n".join([f"- {t['text']}" for t in tweets])
        return f"X API Error: {response.status_code}"
    except Exception as e: return f"X Search Failed: {str(e)}"

@tool("CoinGlass On-chain Data")
def coinglass_data_tool(metric: str) -> str:
    """
    獲取幣圈衍生品清算與費率數據。
    【重要指令】：metric 參數請務必精準輸入字串 "open_interest"。
    """
    api_key = os.getenv("COINGLASS_API_KEY")
    if not api_key: return "System Error: COINGLASS_API_KEY not found."
    headers = {"accept": "application/json", "coinglassSecret": api_key}
    endpoints = {
        "open_interest": "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d"
    }
    url = endpoints.get(metric.lower(), endpoints["open_interest"])
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200: return str(response.json().get("data", []))[:2000]
        return f"CoinGlass Error: {response.status_code}"
    except Exception as e: return f"CoinGlass Failed: {str(e)}"

@tool("CryptoQuant On-chain Data")
def cryptoquant_tool(indicator: str) -> str:
    """
    獲取交易所淨流入或礦工拋售數據。
    【重要指令】：indicator 參數請務必精準輸入字串 "btc-exchange-flows"。
    """
    api_key = os.getenv("CRYPTOQUANT_API_KEY")
    if not api_key: return "System Error: CRYPTOQUANT_API_KEY not found."
    url = f"https://api.cryptoquant.com/v1/{indicator}/current"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            val = response.json().get("result", {}).get("data", [])[:1]
            return f"Indicator {indicator}: {val}"
        return f"CryptoQuant Error: {response.status_code}"
    except Exception as e: return f"CryptoQuant Failed: {str(e)}"

# ==========================================
# 二、 Agent 陣容：四大天王 (OpenRouter)
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        self.crypto_researcher = Agent(
            role="幣圈與宏觀市場研究員",
            goal="搜尋並篩選出 5 則『過去 24 小時內』的高質量幣圈新聞，並強制附上相關的 X (Twitter) 推文來源。",
            backstory="你擁有最強的幣圈嗅覺。你必須避開舊聞與 Spam，並且絕對禁止提供任何與台灣股市 (Taiwanese stocks) 相關的資訊。",
            llm="openrouter/x-ai/grok-4.1-fast", 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        self.ai_researcher = Agent(
            role="前沿 AI 科技研究員",
            goal="搜尋並篩選出 5 則『過去 24 小時內』最新的 AI 產業動態、開源專案與大模型發布新聞。",
            backstory="你是矽谷的科技先驅。你會善用 Tavily 搜尋新聞，並從 X 上捕捉開發者的第一手討論。",
            llm="openrouter/openai/gpt-5.3-codex", 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        self.risk_critic = Agent(
            role="首席風險與邏輯評論員",
            goal="針對 10 則新聞的真實性、市場影響力與潛在風險進行深度審計。",
            backstory="你是華爾街最嚴謹的合夥人。你的短評必須一針見血，注意：絕對不需要給予任何數字評分。",
            llm="openrouter/anthropic/claude-sonnet-4.6", 
            allow_delegation=False,
            verbose=True
        )

        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="結合鏈上實體與衍生品數據，將情報統整為專業的 Telegram Markdown 戰報。",
            backstory="你負責排版定稿。確保每則新聞都有 Agent 的短評，幣圈新聞必須包含 X 推文來源。",
            llm="openrouter/google/gemini-3.1-pro-preview", 
            tools=[coinglass_data_tool, cryptoquant_tool],
            verbose=True
        )

    def run(self):
        crypto_task = Task(
            description=dedent("""
                1. 使用 Tavily 搜尋『過去 24 小時內』的 5 則最新幣圈新聞。
                2. 針對重要主題，必須呼叫 X Real-time Trend Search 觀察推特情緒。
                3. 初稿中除了新聞摘要與短評，**必須明確列出參考的 X 推文原文或來源 (Source)**。
            """),
            expected_output="5 則幣圈新聞初稿，含推特原聲與 Grok 短評。",
            agent=self.crypto_researcher
        )

        ai_task = Task(
            description=dedent("""
                1. 使用 Tavily 搜尋『過去 24 小時內』的 5 則最新 AI 界重大新聞。
                2. 呼叫 X 搜尋工具，捕捉科技圈對於新工具的討論。
                3. 附上 GPT 專屬短評。
            """),
            expected_output="5 則 AI 新聞初稿，含 GPT 短評。",
            agent=self.ai_researcher
        )

        review_task = Task(
            description="審核上述 10 則新聞，給出嚴苛的觀點，不需給予任何分數。",
            expected_output="10 則新聞的純短評批判備忘錄。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        final_report_task = Task(
            description=dedent("""
                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                
                【Telegram Markdown 排版規範】：
                1. 版面分離：分為 `### 📊 市場鏈上數據`、`### 🌐 幣圈前沿`、`### 🧠 AI 視野`。
                2. 鏈上數據區必須包含 CoinGlass 與 CryptoQuant 的狀態。
                3. 每則新聞格式：
                   **【新聞標題】**
                   > 內容摘要...
                   > 🐦 **X 來源/情緒**: (幣圈新聞專用，請貼推文原文)
                   
                   🛸 **Grok** / 🤖 **GPT**: (專屬短評)
                   🛡️ **Claude**: (風險批判短評)
                   💎 **Gemini**: (總結短評)
                4. 善用 Emoji，保留 ASCII 進度條。
            """),
            expected_output="Telegram 最佳化純文字戰報。",
            agent=self.quant_strategist,
            context=[crypto_task, ai_task, review_task]
        )

        crew = Crew(
            agents=[self.crypto_researcher, self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[crypto_task, ai_task, review_task, final_report_task], 
            process=Process.sequential
        )
        return crew.kickoff()

# ==========================================
# 三、 執行與 Telegram 推送邏輯
# ==========================================

if __name__ == "__main__":
    logging.info("Initializing Q-Silicon Four-Core Agent...")
    
    try:
        research_crew = QSiliconResearchCrew()
        final_report = str(research_crew.run())
        logging.info("Report Generation Successful.")
    except Exception as e:
        final_report = f"🚨 Q-Silicon 智庫執行失敗，請檢查系統日誌。\n錯誤訊息：{str(e)}"
        logging.error(f"Execution Failed: {e}")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        bot = telebot.TeleBot(token)
        # Telegram 單則訊息上限為 4096 字元，這裡設定 4000 為安全分段點
        max_length = 4000
        chunks = [final_report[i:i+max_length] for i in range(0, len(final_report), max_length)]
        
        for i, chunk in enumerate(chunks):
            try:
                bot.send_message(chat_id, chunk, parse_mode="Markdown")
                logging.info(f"Telegram Push Success (Chunk {i+1}/{len(chunks)} - Markdown).")
            except Exception as e:
                logging.warning(f"Markdown failed on Chunk {i+1}, falling back to Plain Text: {e}")
                try:
                    bot.send_message(chat_id, chunk)
                    logging.info(f"Telegram Push Success (Chunk {i+1}/{len(chunks)} - Plain Text).")
                except Exception as e2:
                    logging.error(f"Critical Failure sending Chunk {i+1}: {e2}")
    else:
        logging.warning("Telegram configuration missing. Skipping push.")
