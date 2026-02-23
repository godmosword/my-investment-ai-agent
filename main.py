import os
import requests
import telebot  # 需在 requirements.txt 加入 pyTelegramBotAPI
from textwrap import dedent
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# ==========================================
# 一、 外部 API 工具定義 (Tools)
# ==========================================

@tool("Tavily Market Search")
def market_search_tool(query: str) -> str:
    """
    用於搜尋最新的宏觀經濟數據（如 DXY、美債）與數位資產即時新聞。
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "System Error: TAVILY_API_KEY not found."
    
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, search_depth="advanced", max_results=3)
        return str(response.get("results", "No results found."))
    except Exception as e:
        return f"Search Failed: {str(e)}"

@tool("CoinGlass On-chain Data")
def coinglass_data_tool(metric: str) -> str:
    """
    用於獲取加密貨幣衍生品的數據。
    參數 metric 可選值: 'open_interest' (持倉), 'funding_rate' (資金費率), 'liquidation' (清算)。
    """
    api_key = os.getenv("COINGLASS_API_KEY")
    if not api_key:
        return "System Error: COINGLASS_API_KEY not found."
        
    headers = {
        "accept": "application/json",
        "coinglassSecret": api_key
    }
    
    # 根據 metric 對應不同的 V4 API 端點
    endpoints = {
        "open_interest": "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d",
        "funding_rate": "https://open-api-v4.coinglass.com/api/futures/funding-rate/history?symbol=BTC&interval=1d",
        "liquidation": "https://open-api-v4.coinglass.com/api/futures/liquidation/aggregated-history?symbol=BTC&interval=1d"
    }
    
    url = endpoints.get(metric.lower(), endpoints["open_interest"])
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 僅回傳前幾筆數據以避免 context 過長
            return str(data.get("data", []))[:2000]
        return f"CoinGlass API Error: {response.status_code}"
    except Exception as e:
        return f"CoinGlass Request Failed: {str(e)}"


# ==========================================
# 二、 Agent 與 Crew 核心邏輯
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        self.macro_researcher = Agent(
            role="華爾街首席市場研究員",
            goal="追蹤 DXY、美債殖利率變化，並過濾出 3 則具備邊際影響力的市場新聞。",
            backstory=dedent("""
                你是一名專精於跨資產連動的華爾街研究員。
                你的分析客觀冷靜，只描述『預期差』與『市場定價』，絕不使用情緒化字眼。
                核心指令：分析範疇專注於全球宏觀與數位資產，嚴禁包含或建議任何台灣股市 (TAIEX) 相關的資訊。
            """),
            llm="xai/grok-4-1-fast-reasoning",
            tools=[market_search_tool],
            allow_delegation=False,
            verbose=True
        )

        self.quant_strategist = Agent(
            role="機構宏觀策略分析師",
            goal="深度解讀 CoinGlass 的數據並彙整最終的 Institutional Daily Digest。",
            backstory=dedent("""
                你代表頂級投行的量化水準。你的任務是揭示市場微觀結構的偏離。
                寫作規範：嚴禁使用『此外、總結』等 AI 廢話。
                維持 80% 淺顯宏觀概況與 20% 高深結構分析的內容比例。
            """),
            llm="google/gemini-3.1-pro-preview",
            tools=[coinglass_data_tool],
            allow_delegation=False,
            verbose=True
        )

    def run(self):
        compile_report_task = Task(
            description=dedent("""
                請主動運用工具擷取最新數據，並撰寫一份 [Q-Silicon Institutional Research] Daily Brief。
                架構：
                #### 一、 宏觀環境觀測 (Macro Sentiment)
                #### 二、 即時新聞摘要 (Market Catalysts)
                #### 三、 鏈上結構分析 (On-chain Dynamics)
                #### 四、 策略分析師備忘錄 (Executive Summary)
            """),
            expected_output="一份符合華爾街機構標準、不帶情緒且排版精確的 Markdown 報告。",
            agent=self.quant_strategist
        )

        crew = Crew(
            agents=[self.macro_researcher, self.quant_strategist],
            tasks=[compile_report_task],
            process=Process.sequential
        )
        return crew.kickoff()


if __name__ == "__main__":
    print("Initializing Q-Silicon Institutional Research Agent...")
    research_crew = QSiliconResearchCrew()
    final_report = str(research_crew.run())
    
    print("\n=== Q-Silicon Report Generated ===\n")
    print(final_report)
    
    # --- Telegram 發送邏輯 ---
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        try:
            bot = telebot.TeleBot(token)
            # 使用 Markdown 格式發送，確保標題和加粗效果
            bot.send_message(chat_id, final_report, parse_mode="Markdown")
            print("Report sent to Telegram successfully.")
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")
    else:
        print("Telegram configuration missing. Skipping broadcast.")
