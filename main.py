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
# 一、 外部 API 工具定義 (含 AI 算力與宏觀指標)
# ==========================================

@tool("AI Momentum Analyzer")
def ai_momentum_tool(metric: str) -> str:
    """獲取 AI 產業核心指標。metric 請輸入 'gpu_pricing' (H100/B200 租賃價) 或 'model_benchmarks' (排名)。"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key: return "TAVILY_API_KEY not found."
    from tavily import TavilyClient
    client = TavilyClient(api_key=api_key)
    
    queries = {
        "gpu_pricing": "current hourly rental price for NVIDIA H100 and B200 GPUs Feb 2026",
        "model_benchmarks": "latest LMSYS Chatbot Arena ELO rankings for GPT-5, Claude 4, Gemini 3"
    }
    query = queries.get(metric.lower(), "latest AI compute economy")
    try:
        response = client.search(query=query, search_depth="advanced", max_results=3)
        return str(response.get("results", "No data found."))
    except Exception as e: return f"AI Tool Failed: {str(e)}"

@tool("Macro Liquidity Tracker")
def macro_liquidity_tool(indicator: str) -> str:
    """獲取全球宏觀指標。indicator 請輸入 'M2' (貨幣供應), 'CPI' (通膨) 或 'DXY' (美指)。"""
    fred_key = os.getenv("FRED_API_KEY")
    if not fred_key:
        # Fallback to Tavily if FRED key is missing
        api_key = os.getenv("TAVILY_API_KEY")
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        try:
            res = client.search(query=f"current {indicator} index value Feb 2026", max_results=1)
            return str(res.get("results", "Macro data not found."))
        except: return "Macro Search Failed."

    series_map = {"M2": "M2SL", "CPI": "CPIAUCSL", "DXY": "DTWEXBGS"}
    series_id = series_map.get(indicator.upper(), "M2SL")
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_key}&file_type=json&sort_order=desc&limit=1"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            latest = response.json().get("observations", [{}])[0]
            return f"{indicator}: {latest.get('value')} (Date: {latest.get('date')})"
        return f"FRED API Error: {response.status_code}"
    except Exception as e: return f"Macro Tracker Failed: {str(e)}"

@tool("Tavily Market Search")
def market_search_tool(query: str) -> str:
    """搜尋全球即時新聞。"""
    api_key = os.getenv("TAVILY_API_KEY")
    from tavily import TavilyClient
    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, search_depth="advanced", max_results=5, topic="news", days=1)
    return str(response.get("results", []))

@tool("X Real-time Trend Search")
def x_search_tool(query: str) -> str:
    """搜尋 X 情緒。"""
    bearer_token = os.getenv("X_BEARER_TOKEN")
    url = f"https://api.twitter.com/2/tweets/search/recent?query={quote(query)}&max_results=10"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = requests.get(url, headers=headers, timeout=10)
    tweets = response.json().get("data", [])
    return "\n".join([f"- {t['text']}" for t in tweets])

@tool("CoinGlass On-chain Data")
def coinglass_data_tool(metric: str) -> str:
    """獲取幣圈衍生品數據。"""
    api_key = os.getenv("COINGLASS_API_KEY")
    headers = {"accept": "application/json", "coinglassSecret": api_key}
    url = "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d"
    response = requests.get(url, headers=headers, timeout=10)
    return str(response.json().get("data", []))[:2000]

@tool("CryptoQuant On-chain Data")
def cryptoquant_tool(indicator: str) -> str:
    """獲取交易所流入數據。"""
    api_key = os.getenv("CRYPTOQUANT_API_KEY")
    url = "https://api.cryptoquant.com/v1/btc/exchange-flows/inflow?limit=1"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json().get("result", {}).get("data", [])
        return f"BTC Inflow: {data[0].get('inflow')} BTC" if data else "No data."
    return "API 403 or Error."

# ==========================================
# 二、 Agent 陣容：原生 2026 旗艦配置
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        
        # 🛸 Grok 4.1-Fast Reasoning (直連 xAI)
        grok_latest = LLM(
            model="xai/grok-4-1-fast-reasoning", 
            api_key=os.getenv("XAI_API_KEY")
        )
        
        # 🤖 GPT-5.3-Codex (直連 OpenAI)
        gpt_latest = LLM(
            model="openai/gpt-5.3-codex", 
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # 🛡️ Claude 4.6 (經由 OpenRouter)
        claude_latest = LLM(
            model="openrouter/anthropic/claude-sonnet-4.6", 
            api_key=os.getenv("OPENROUTER_API_KEY"),
            assistant_prefill=False
        )
        
        # 💎 Gemini 3.1-Pro-Preview (直連 Google)
        gemini_latest = LLM(
            model="gemini/gemini-3.1-pro-preview", 
            api_key=os.getenv("GEMINI_API_KEY")
        )

        self.crypto_researcher = Agent(
            role="幣圈與宏觀市場研究員",
            goal="挑選 5 則幣圈新聞並分析宏觀 M2/DXY 數據指標。",
            backstory="您擅長交叉比對鏈上流向與全球流動性，Grok 4.1 是您的核心。",
            llm=grok_latest, 
            tools=[market_search_tool, x_search_tool, macro_liquidity_tool],
            verbose=True
        )

        self.ai_researcher = Agent(
            role="前沿 AI 科技研究員",
            goal="挑選 5 則最新 AI 動態並分析 GPU 租賃成本與模型性能排名。",
            backstory="您關注矽谷核心動態，GPT-5.3 是您的核心。您追求極致時效。",
            llm=gpt_latest, 
            tools=[market_search_tool, x_search_tool, ai_momentum_tool],
            verbose=True
        )

        self.risk_critic = Agent(
            role="首席風險與邏輯評論員",
            goal="針對數據進行毒舌審計。Claude 是您的思維核心。",
            backstory="您負責潑冷水，揭露虛假的指標背離。一針見血。",
            llm=claude_latest, 
            allow_delegation=False,
            verbose=True
        )

        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="整合『精準數據儀表板』與 Agent 短評。Gemini 3.1 是您的靈魂。",
            backstory="您負責最後排版，嚴禁廢話。僅列出有實際參與評述的 Agent。",
            llm=gemini_latest, 
            tools=[coinglass_data_tool, cryptoquant_tool],
            verbose=True
        )

    def run(self):
        crypto_task = Task(
            description="分析 24 小時內 M2 或 DXY 指標對 BTC 的影響，挑選 5 則幣圈新聞。",
            expected_output="含宏觀指標與 5 則新聞及 Grok 評論的初稿。",
            agent=self.crypto_researcher
        )

        ai_task = Task(
            description="獲取 H100 價格或 LMSYS 模型排名，列出 5 則最新 AI 突破。",
            expected_output="含 AI 經濟指標與 5 則新聞及 GPT 評論的初稿。",
            agent=self.ai_researcher
        )

        review_task = Task(
            description="對比數據指標與新聞真實性，給出嚴苛批判。",
            expected_output="數據審計備忘錄。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        final_report_task = Task(
            description=dedent("""
                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                
                【儀表板區塊】：
                - AI 算力價格/排名
                - 宏觀流動性 (M2/DXY)
                - 幣圈鏈上 (OI/Inflow)
                
                【評論規則】：
                1. 幣圈新聞：僅顯示 🛸 **Grok**、🛡️ **Claude** 與 💎 **主編**。
                2. AI 新聞：僅顯示 🤖 **GPT**、🛡️ **Claude** 與 💎 **主編**。
                
                🚨 嚴禁輸出任何思考過程。
            """),
            expected_output="Telegram 最佳化、帶有精準儀表板的專業戰報。",
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
    logging.info("Initializing 2026 Q-Silicon Ultimate Agent...")
    
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
        chunks = [final_report[i:i+4000] for i in range(0, len(final_report), 4000)]
        for chunk in chunks:
            try:
                bot.send_message(chat_id, chunk, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, chunk)
    else:
        logging.warning("Telegram configuration missing. Skipping push.")
