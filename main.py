import os
import requests
import telebot
import logging
from urllib.parse import quote
from textwrap import dedent
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# 載入環境變數
load_dotenv()

# 🚀 強制注入金鑰，確保 Google 原生 SDK 驗證通過
if os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")

# 設定日誌
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
            return "CryptoQuant API 403: 權限不足，請忽略此數據直接撰寫報告。"
        return f"CryptoQuant Error: {response.status_code}"
    except Exception as e: return f"CryptoQuant Failed: {str(e)}"

# ==========================================
# 二、 Agent 陣容：原生 API 識別優化版
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        
        # 🛸 Grok：直連 xAI 原生 API
        grok_latest = LLM(
            model="xai/grok-4.1-fast", 
            api_key=os.getenv("XAI_API_KEY"),
            assistant_prefill=False
        )
        
        # 🤖 GPT：直連 OpenAI 原生 API (修正 ID 識別)
        gpt_latest = LLM(
            model="gpt-5.3-codex", 
            api_key=os.getenv("OPENAI_API_KEY"),
            assistant_prefill=False
        )
        
        # 🛡️ Claude：走 OpenRouter 中轉
        claude_latest = LLM(
            model="openrouter/anthropic/claude-sonnet-4.6", 
            api_key=os.getenv("OPENROUTER_API_KEY"),
            assistant_prefill=False
        )
        
        # 💎 Gemini：直連 Google 原生 API (使用 GEMINI_API_KEY)
        gemini_latest = LLM(
            model="gemini/gemini-3.1-pro-preview", 
            api_key=os.getenv("GEMINI_API_KEY"),
            assistant_prefill=False
        )

        self.crypto_researcher = Agent(
            role="幣圈與宏觀市場研究員",
            goal="挑選 5 則具影響力的幣圈新聞，綜合 Tavily 與 X 情緒。若 X 無熱度則淘汰。",
            backstory="您擁有最強的幣圈嗅覺，嚴禁台股內容。Grok 是您的思維核心。",
            llm=grok_latest, 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        self.ai_researcher = Agent(
            role="前沿 AI 科技研究員",
            goal="搜尋並篩選出 5 則『12小時內』最新、最具突破性的 AI 產業動態。",
            backstory=dedent("""
                您是矽谷科技先驅，GPT 是您的思維核心。
                1. 您的關鍵字必須包含 "announced today", "just released"。
                2. 您必須交叉比對 X 討論，若該新聞在 X 上已經沒人討論，請立即視為舊聞捨棄。
                3. 您只追求最領先、剛發布的新消息。
            """),
            llm=gpt_latest, 
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        self.risk_critic = Agent(
            role="首席風險與邏輯評論員",
            goal="針對 10 則新聞進行嚴苛審計，揭露炒作風險。",
            backstory="華爾街合夥人。一針見血，不給數字評分。Claude 是您的思維核心。",
            llm=claude_latest, 
            allow_delegation=False,
            verbose=True
        )

        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="整合數據與各 Agent 的觀點，輸出專業戰報。🚨僅列出有實際參與評述的 Agent。",
            backstory="您負責排版。🚨絕對禁止輸出思考過程。Gemini 是您的思維核心。",
            llm=gemini_latest, 
            tools=[coinglass_data_tool, cryptoquant_tool],
            verbose=True
        )

    def run(self):
        crypto_task = Task(
            description="搜尋 24 小時內幣圈新聞，比對 X 情緒，篩選 5 則並附上 X 來源。",
            expected_output="5 則含推特原聲與 Grok 短評的新聞初稿。",
            agent=self.crypto_researcher
        )

        ai_task = Task(
            description="搜尋『過去 12 小時內』AI 突破，比對 X 當下熱度，列出 5 則並附上 X 來源。",
            expected_output="5 則時效性最強的 AI 新聞初稿，含 X 來源與 GPT 短評。",
            agent=self.ai_researcher
        )

        review_task = Task(
            description="審核上述 10 則新聞，給出毒舌批判。不給分。",
            expected_output="10 則新聞的批判備忘錄。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        final_report_task = Task(
            description=dedent("""
                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                
                🚨🚨🚨【動態過濾排版規則】🚨🚨🚨
                每一則新聞下方，請『分行』且『僅列出參與該則新聞審核之 Agent』的觀點：
                1. 幣圈新聞：請顯示 🛸 **Grok**、🛡️ **Claude** 與 💎 **主編** 的觀點。
                2. AI 新聞：請顯示 🤖 **GPT**、🛡️ **Claude** 與 💎 **主編** 的觀點。
                3. **禁止**在該則新聞下方出現未參與 Agent 的標籤（例如：幣圈新聞下不可出現 GPT 區塊）。
                
                🚨 嚴禁輸出任何思考過程或 "(Done)" 字眼。
            """),
            expected_output="Telegram 最佳化、動態過濾觀點的純淨 Markdown 戰報文本。",
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
    logging.info("Initializing Q-Silicon Ultimate Native-API Agent...")
    
    try:
        research_crew = QSiliconResearchCrew()
        final_report = str(research_crew.run())
        logging.info("Report Generation Successful.")
    except Exception as e:
        final_report = f"🚨 Q-Silicon 智庫執行失敗，請檢查日誌。\n錯誤訊息：{str(e)}"
        logging.error(f"Execution Failed: {e}")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        bot = telebot.TeleBot(token)
        chunks = [final_report[i:i+4000] for i in range(0, len(final_report), 4000)]
        for chunk in chunks:
            try:
                bot.send_message(chat_id, chunk, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, chunk)
    else:
        logging.warning("Telegram configuration missing. Skipping push.")
