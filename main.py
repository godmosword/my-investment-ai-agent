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
    """用於搜尋最新的宏觀經濟數據與數位資產即時新聞。"""
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
    """獲取加密貨幣衍生品數據：open_interest, funding_rate, liquidation。"""
    api_key = os.getenv("COINGLASS_API_KEY")
    if not api_key:
        return "System Error: COINGLASS_API_KEY not found."
    headers = {"accept": "application/json", "coinglassSecret": api_key}
    endpoints = {
        "open_interest": "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d",
        "funding_rate": "https://open-api-v4.coinglass.com/api/futures/funding-rate/history?symbol=BTC&interval=1d",
        "liquidation": "https://open-api-v4.coinglass.com/api/futures/liquidation/aggregated-history?symbol=BTC&interval=1d"
    }
    url = endpoints.get(metric.lower(), endpoints["open_interest"])
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return str(response.json().get("data", []))[:2000]
        return f"CoinGlass API Error: {response.status_code}"
    except Exception as e:
        return f"CoinGlass Request Failed: {str(e)}"

# ==========================================
# 二、 Agent 與 Crew 核心邏輯
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        # 1. 宏觀研究員 (Grok 4.1)
        self.macro_researcher = Agent(
            role="華爾街首席市場研究員",
            goal="捕捉具備『市場爆點』的新聞敘事與全球宏觀數據變化。",
            backstory=dedent("""
                你具備敏銳的市場嗅覺。專注於催化劑分析，嚴禁提及台灣股市。
            """),
            llm="xai/grok-4-1-fast-reasoning",
            tools=[market_search_tool],
            verbose=True
        )

        # 2. 策略分析師 (Gemini 3.1)
        self.quant_strategist = Agent(
            role="機構宏觀策略分析師",
            goal="將鏈上數據轉化為視覺化的指標儀表板，並產出深度的 80/20 專業報告。",
            backstory=dedent("""
                你擅長製作 Market Dashboard。維持華爾街冷靜風格，不說廢話。
            """),
            llm="google/gemini-3.1-pro-preview",
            tools=[coinglass_data_tool],
            verbose=True
        )

    def run(self): # <--- 修正：現在正確縮排在類別內部
        research_task = Task(
            description=dedent("""搜尋宏觀數據與 3 則具『敘事轉折感』的新聞，嚴禁包含台股資訊。"""),
            expected_output="宏觀趨勢與新聞催化劑摘要。",
            agent=self.macro_researcher
        )

        compile_report_task = Task(
            description=dedent("""
                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                必須包含：
                1. 【📊 Market Dashboard】：使用文字模擬指標呈現數據。
                2. 四大標準結構排版。
            """),
            expected_output="一份具備視覺化指標且不帶情緒的 Markdown 報告。",
            agent=self.quant_strategist
        )

        crew = Crew(
            agents=[self.macro_researcher, self.quant_strategist],
            tasks=[research_task, compile_report_task], 
            process=Process.sequential
        )
        return crew.kickoff()

# ==========================================
# 三、 執行與發送邏輯
# ==========================================

if __name__ == "__main__":
    print("Initializing Q-Silicon Institutional Research Agent...")
    research_crew = QSiliconResearchCrew()
    final_report = str(research_crew.run())
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        bot = telebot.TeleBot(token)
        try:
            bot.send_message(chat_id, final_report, parse_mode="Markdown")
            print("Report sent via Markdown.")
        except Exception as e:
            bot.send_message(chat_id, final_report)
            print("Fallback to Plain Text sent.")
    else:
        print("Telegram config missing.")
