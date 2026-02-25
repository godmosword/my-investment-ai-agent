import os
import requests
import telebot
from textwrap import dedent
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

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
    """搜尋 X (Twitter) 上最新的討論情緒。"""
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token: return "System Error: X_BEARER_TOKEN not found."
    url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10"
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
    """獲取加密貨幣衍生品數據：open_interest, funding_rate, liquidation。"""
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

# ==========================================
# 二、 Agent 陣容：四大天王 (OpenRouter)
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        # 1. 幣圈偵察兵 (Grok)
        self.crypto_researcher = Agent(
            role="幣圈與宏觀市場研究員",
            goal="搜尋並篩選出 5 則『過去 24 小時內』的高質量幣圈新聞，並強制附上相關的 X (Twitter) 推文來源與社群情緒。",
            backstory="你擁有最強的幣圈嗅覺。你必須避開舊聞與 Spam，並且絕對不提供台灣股市相關的內容。",
            llm="openrouter/x-ai/grok-4.1-fast", 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        # 2. AI 科技研究員 (ChatGPT)
        self.ai_researcher = Agent(
            role="前沿 AI 科技研究員",
            goal="搜尋並篩選出 5 則『過去 24 小時內』最新的 AI 產業動態與大模型發布新聞。",
            backstory="你是矽谷的科技先驅，專注於挖掘最具突破性的 AI 資訊與編程技術發展。",
            llm="openrouter/openai/gpt-5.3-codex", 
            tools=[market_search_tool],
            verbose=True
        )

        # 3. 首席風控評論員 (Claude)
        self.risk_critic = Agent(
            role="首席風險與邏輯評論員",
            goal="針對 10 則新聞（幣圈+AI）的真實性、市場影響力與潛在風險進行深度審計。",
            backstory="你是華爾街最嚴謹的合夥人，你的短評必須一針見血，揭露市場炒作與隱患。不需要給予任何數字評分。",
            llm="openrouter/anthropic/claude-sonnet-4.6", 
            allow_delegation=False,
            verbose=True
        )

        # 4. 機構策略分析師 (Gemini)
        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="結合鏈上數據，將所有情報統整為專業的 Telegram Markdown 戰報。",
            backstory="你負責排版定稿，善用 Markdown 語法來增加可讀性。你必須確保每則新聞都有 Agent 們的獨立短評，且幣圈新聞必須包含 X 推文來源。",
            llm="openrouter/google/gemini-3.1-pro-preview", 
            tools=[coinglass_data_tool],
            verbose=True
        )

    def run(self):
        # 任務一：幣圈新聞與 X 觀測 (強制列出 Source)
        crypto_task = Task(
            description=dedent("""
                1. 使用 Tavily 搜尋『過去 24 小時內』的 5 則最新幣圈新聞。
                2. 針對重要主題，必須呼叫 X Real-time Trend Search 觀察推特情緒。
                3. 在你的初稿中，除了新聞摘要與你的專屬短評外，**必須明確列出你參考的 X 推文原文或來源 (Source)**。
            """),
            expected_output="5 則今日幣圈新聞初稿，包含推特原聲 (Source) 與 Grok 短評。",
            agent=self.crypto_researcher
        )

        # 任務二：AI 科技新聞
        ai_task = Task(
            description=dedent("""
                使用 Tavily 搜尋『過去 24 小時內』的 5 則最新 AI 人工智慧界重大新聞。
                附上發布時間與你的 GPT 專屬短評。
            """),
            expected_output="5 則今日 AI 界新聞初稿，包含 GPT 短評。",
            agent=self.ai_researcher
        )

        # 任務三：全面審核 (無評分)
        review_task = Task(
            description="對 Grok 抓取的 5 則幣圈新聞與 GPT 抓取的 5 則 AI 新聞進行深度風險評估。給出你嚴苛的觀點，不需給予任何分數。",
            expected_output="10 則新聞的批判備忘錄（純短評，無評分）。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        # 任務四：最終排版 (恢復 Telegram Markdown)
        final_report_task = Task(
            description=dedent("""
                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                
                【Telegram Markdown 排版規範】：
                1. 版面分離：分為 `### 📊 市場鏈上數據`、`### 🌐 幣圈前沿`、`### 🧠 AI 視野` 三大區塊。
                2. 每一則新聞都必須採用以下格式呈現：
                
                   **【新聞標題】**
                   > 內容摘要...
                   > 🐦 **X 來源/情緒**: (僅幣圈新聞需要，請直接貼上推文原文或重點來源)
                   
                   🛸 **Grok** / 🤖 **GPT**: (專屬短評)
                   🛡️ **Claude**: (風險批判短評)
                   💎 **Gemini**: (總結短評)
                   
                3. 善用 Emoji 來增加閱讀性。
                4. 保留 ASCII 進度條 `[████░░░░]` 作為數據呈現。
            """),
            expected_output="一份專為 Telegram 最佳化、包含 Markdown 語法與推文來源的純文字四核戰報。",
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
    print("Initializing Q-Silicon Four-Core Agent for Telegram...")
    research_crew = QSiliconResearchCrew()
    final_report = str(research_crew.run())
    
    print("\n=== Report Generated ===\n")
    print(final_report)
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        bot = telebot.TeleBot(token)
        try:
            bot.send_message(chat_id, final_report, parse_mode="Markdown")
            print("Telegram Push Success (Markdown).")
        except Exception as e:
            print(f"Markdown failed, falling back to Plain Text: {e}")
            try:
                bot.send_message(chat_id, final_report)
                print("Telegram Push Success (Plain Text).")
            except Exception as e2:
                print(f"Critical Failure: {e2}")
    else:
        print("Telegram configuration missing. Skipping push.")
