import os
import requests
import telebot
import logging
from urllib.parse import quote
from textwrap import dedent
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# 載入本地端 .env 變數
load_dotenv()

# 設定基礎日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# 一、 外部 API 工具定義
# ==========================================

@tool("Tavily Market Search")
def market_search_tool(query: str) -> str:
    """搜尋全球宏觀、數位資產與『AI科技』即時新聞。"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key: return "System Error: TAVILY_API_KEY not found."
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        # 強制只抓取過去 24 小時內的新聞，並增加搜尋深度
        response = client.search(query=query, search_depth="advanced", max_results=5, topic="news", days=1)
        return str(response.get("results", "No results found."))
    except Exception as e: return f"Tavily Failed: {str(e)}"

@tool("X Real-time Trend Search")
def x_search_tool(query: str) -> str:
    """搜尋 X (Twitter) 上最新的討論情緒與科技圈發文。"""
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token: return "System Error: X_BEARER_TOKEN not found."
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
    """獲取幣圈衍生品數據。"""
    api_key = os.getenv("COINGLASS_API_KEY")
    if not api_key: return "System Error: COINGLASS_API_KEY not found."
    headers = {"accept": "application/json", "coinglassSecret": api_key}
    url = "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200: return str(response.json().get("data", []))[:2000]
        return f"CoinGlass Error: {response.status_code}"
    except Exception as e: return f"CoinGlass Failed: {str(e)}"

@tool("CryptoQuant On-chain Data")
def cryptoquant_tool(indicator: str) -> str:
    """獲取比特幣交易所單向流入數據。"""
    api_key = os.getenv("CRYPTOQUANT_API_KEY")
    if not api_key: return "System Error: CRYPTOQUANT_API_KEY not found."
    url = "https://api.cryptoquant.com/v1/btc/exchange-flows/inflow?limit=1"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json().get("result", {}).get("data", [])
            if data: return f"BTC Inflow: {data[0].get('inflow')} BTC"
            return "No data found."
        elif response.status_code == 403:
            return "CryptoQuant API 403: 權限不足，請忽略此數據直接繼續撰寫報告。"
        return f"CryptoQuant Error: {response.status_code}"
    except Exception as e: return f"CryptoQuant Failed: {str(e)}"

# ==========================================
# 二、 Agent 陣容：堅持最新模型 + 防崩潰配置
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        
        # 👑 頂配模型陣容 (強制關閉 Prefill 避開 Google 節點限制)
        grok_latest = LLM(model="openrouter/x-ai/grok-4.1-fast", assistant_prefill=False)
        gpt_latest = LLM(model="openrouter/openai/gpt-5.3-codex", assistant_prefill=False)
        claude_latest = LLM(model="openrouter/anthropic/claude-sonnet-4.6", assistant_prefill=False)
        gemini_latest = LLM(model="openrouter/google/gemini-3.1-pro-preview", assistant_prefill=False)

        self.crypto_researcher = Agent(
            role="幣圈與宏觀市場研究員",
            goal="挑選最具影響力的 5 則幣圈新聞，綜合 Tavily 與 X 情緒。若 X 無熱度則淘汰。",
            backstory="您擁有最強的幣圈嗅覺。如果一則新聞在 X 上沒有引起真實的社群討論，您會視為舊聞並捨棄。嚴禁台股內容。",
            llm=grok_latest, 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        self.ai_researcher = Agent(
            role="前沿 AI 科技研究員",
            goal="搜尋並篩選出 5 則『24 小時內』最新、最具突破性的 AI 產業動態。",
            backstory=dedent("""
                您是矽谷科技先驅，對『時效性』有近乎偏執的要求。
                1. 您的搜尋關鍵字必須包含 "today", "breaking", "just announced"。
                2. 您必須交叉比對 X 上的開發者討論，如果該新聞在 X 上是 2 天前就有的討論，請立即捨棄。
                3. 您的目標是找到那些『剛發布不到 12 小時』的震撼消息。
            """),
            llm=gpt_latest, 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        self.risk_critic = Agent(
            role="首席風險與邏輯評論員",
            goal="針對 10 則新聞進行嚴苛的毒舌審計，揭露市場炒作與潛在風險。",
            backstory="華爾街合夥人。您的工作是潑冷水，分析為什麼這則新聞可能是騙局或過度吹捧。不給數字評分。",
            llm=claude_latest, 
            allow_delegation=False,
            verbose=True
        )

        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="將所有 Agent 的觀點整合為專業戰報。🚨必須分開列出不同 Agent 的評論。",
            backstory="您負責最後排版，確保每一則新聞都有 X 推文來源，並強制分行顯示 Grok, GPT, Claude 的觀點。",
            llm=gemini_latest, 
            tools=[coinglass_data_tool, cryptoquant_tool],
            verbose=True
        )

    def run(self):
        crypto_task = Task(
            description="搜尋 24 小時內幣圈新聞，比對 X 情緒，挑選 5 則並明確標記 X 來源帳號與推文亮點。",
            expected_output="5 則含推特原聲與 Grok 短評的新聞初稿。",
            agent=self.crypto_researcher
        )

        ai_task = Task(
            description=dedent("""
                搜尋『過去 12-24 小時內』的 AI 突破消息。
                1. 搜尋時請使用 "latest AI model release today" 或 "AI breaking news hours ago"。
                2. 必須比對 X 上是否有『當下』的熱烈討論，捨棄所有已被冷落的舊資訊。
                3. 挑選 5 則最新動態並附上 X 來源帳號。
            """),
            expected_output="5 則極具時效性的 AI 新聞初稿，含 X 推特原聲與 GPT 短評。",
            agent=self.ai_researcher
        )

        review_task = Task(
            description="審核上述 10 則新聞，給出嚴苛批判。不給分。",
            expected_output="10 則新聞的批判備忘錄。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        final_report_task = Task(
            description=dedent("""
                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                
                【強制排版格式範例】：
                **【新聞標題】**
                > 內容摘要...
                > 🐦 **X 來源**: @帳號 (推文內容摘要)
                
                🛸 **Grok** / 🤖 **GPT**: (對應 Agent 的短評)
                🛡️ **Claude**: (風險批判短評)
                💎 **主編**: (您的綜合結語)
                
                🚨 注意：嚴禁將評論混在一起，每一位 Agent 的標誌符號後都必須換行顯示其觀點。禁止輸出思考過程。
            """),
            expected_output="Telegram 最佳化、意見分立的純淨 Markdown 戰報文本。",
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
# 三、 執行與 Telegram 推送
# ==========================================

if __name__ == "__main__":
    logging.info("Initializing Q-Silicon Ultimate High-End Stable Agent...")
    
    try:
        research_crew = QSiliconResearchCrew()
        final_report = str(research_crew.run())
        logging.info("Report Generation Successful.")
    except Exception as e:
        final_report = f"🚨 Q-Silicon 智庫執行失敗，請檢查日誌。\n錯誤：{str(e)}"
        logging.error(f"Execution Failed: {e}")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        bot = telebot.TeleBot(token)
        # 每段訊息不超過 4000 字以符合 Telegram 限制
        chunks = [final_report[i:i+4000] for i in range(0, len(final_report), 4000)]
        for chunk in chunks:
            try:
                bot.send_message(chat_id, chunk, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, chunk)
    else:
        logging.warning("Telegram configuration missing. Skipping push.")
