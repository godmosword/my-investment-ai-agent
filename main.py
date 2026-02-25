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
        # 強制只抓取過去 24 小時內的新聞
        response = client.search(query=query, search_depth="advanced", max_results=5, topic="news", days=1)
        return str(response.get("results", "No results found."))
    except Exception as e: return f"Tavily Failed: {str(e)}"

@tool("X Real-time Trend Search")
def x_search_tool(query: str) -> str:
    """搜尋 X (Twitter) 上最新的討論情緒與科技圈發文。"""
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
    """獲取幣圈衍生品清算與費率數據。"""
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
    """獲取交易所淨流入或礦工拋售數據 (如: btc-exchange-flows)。"""
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
        # 1. 幣圈偵察兵 (Grok)
        self.crypto_researcher = Agent(
            role="幣圈與宏觀市場研究員",
            goal="搜尋並篩選出 5 則『過去 24 小時內』的高質量幣圈新聞，並強制附上相關的 X (Twitter) 推文來源。",
            backstory="你擁有最強的幣圈嗅覺。你必須避開舊聞與 Spam，並且絕對禁止提供任何與台灣股市 (Taiwanese stocks) 相關的資訊。",
            llm="openrouter/x-ai/grok-4.1-fast", 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        # 2. AI 科技研究員 (ChatGPT)
        self.ai_researcher = Agent(
            role="前沿 AI 科技研究員",
            goal="搜尋並篩選出 5 則『過去 24 小時內』最新的 AI 產業動態、開源專案與大模型發布新聞。",
            backstory="你是矽谷的科技先驅，專注於挖掘最具突破性的 AI 資訊。你會善用 Tavily 搜尋新聞，並從 X 上捕捉開發者的第一手討論。",
            llm="openrouter/openai/gpt-5.3-codex", 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        # 3. 首席風控評論員 (Claude)
        self.risk_critic = Agent(
            role="首席風險與邏輯評論員",
            goal="針對 10 則新聞（幣圈+AI）的真實性、市場影響力與潛在風險進行深度審計。",
            backstory="你是華爾街最嚴謹的合夥人，你的短評必須一針見血，揭露市場炒作與隱患。注意：絕對不需要給予任何數字評分。",
            llm="openrouter/anthropic/claude-sonnet-4.6", 
            allow_delegation=False,
            verbose=True
        )

        # 4. 機構策略分析師 (Gemini)
        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="結合鏈上實體與衍生品數據，將情報統整為專業的 Telegram Markdown 戰報。",
            backstory="你負責排版定稿。你必須確保每則新聞都有 Agent 們的獨立短評，且幣圈新聞必須包含 X 推文來源。",
            llm="openrouter/google/gemini-3.1-pro-preview", 
            tools=[coinglass_data_tool, cryptoquant_tool],
            verbose=True
        )

    def run(self):
        # 任務一：幣圈新聞與 X 觀測 (Grok)
        crypto_task = Task(
            description=dedent("""
                1. 使用 Tavily 搜尋『過去 24 小時內』的 5 則最新幣圈新聞。
                2. 針對重要主題，必須呼叫 X Real-time Trend Search 觀察推特情緒。
                3. 初稿中除了新聞摘要與你的專屬短評，**必須明確列出你參考的 X 推文原文或來源 (Source)**。
            """),
            expected_output="5 則今日幣圈新聞初稿，包含推特原聲 (Source) 與 Grok 短評。",
            agent=self.crypto_researcher
        )

        # 任務二：AI 科技新聞 (ChatGPT)
        ai_task = Task(
            description=dedent("""
                1. 使用 Tavily 搜尋『過去 24 小時內』的 5 則最新 AI 人工智慧界重大新聞 (例如新模型、工具發表)。
                2. 呼叫 X 搜尋工具，捕捉科技圈對於這些新工具的討論。
                3. 附上發布時間與你的 GPT 專屬短評。
            """),
            expected_output="5 則今日 AI 界新聞初稿，包含 GPT 短評。",
            agent=self.ai_researcher
        )

        # 任務三：全面審核 (Claude，無評分)
        review_task = Task(
            description="對 Grok 抓取的 5 則幣圈新聞與 GPT 抓取的 5 則 AI 新聞進行深度風險評估。給出你嚴苛的觀點，不需給予任何分數。",
            expected_output="10 則新聞的批判備忘錄（純短評，無評分）。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        # 任務四
