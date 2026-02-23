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
    """用於搜尋最新的全球宏觀數據與數位資產即時新聞。"""
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
# 二、 三大 Agent 陣容：Grok + Gemini + OpenAI
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        # 1. 宏觀偵察兵 (Grok 4.1)
        self.macro_researcher = Agent(
            role="華爾街首席市場研究員",
            goal="捕捉具備『市場爆點』的宏觀敘事。使用 Grok-4-1。",
            backstory="具備最強新聞敏感度，專注於催化劑分析。嚴禁提及台股。",
            llm="xai/grok-4-1-fast-reasoning",
            tools=[market_search_tool],
            verbose=True
        )

        # 2. 數據精算師 (Gemini 3.1)
        self.quant_strategist = Agent(
            role="機構宏觀策略分析師",
            goal="提供鏈上數據深度解讀，並整合最終意見產出報告。使用 Gemini-3.1。",
            backstory="負責製作 Market Dashboard。維持華爾街冷靜風格，不說廢話。",
            llm="google/gemini-3.1-pro-preview",
            tools=[coinglass_data_tool],
            verbose=True
        )

        # 3. 首席風控評論員 (使用指定測試模型: GPT-5.2-Pro)
        self.risk_critic = Agent(
            role="首席風險評論員 (Chief Risk Critic)",
            goal="挑戰前兩者的邏輯漏洞，並給予 1-10 分的最終質量評分。",
            backstory=dedent("""
                你使用 OpenAI 最新的測試模型 GPT-5.2-Pro。
                身為華爾街合夥人，你負責執行最嚴苛的審計。
                你會挑戰 Grok 的市場解讀與 Gemini 的數據推論。
                你必須給出具體的批判建議，並在最後給予報告嚴謹度評分。
            """),
            llm="openai/gpt-5.2-pro", # <--- 根據你的要求進行測試
            allow_delegation=True,
            verbose=True
        )

    def run(self):
        # 任務一：情報初稿 (Grok 啟動)
        research_task = Task(
            description="搜尋宏觀趨勢與具備衝擊力的新聞，嚴禁包含台股資訊。",
            expected_output="市場研究初稿。",
            agent=self.macro_researcher
        )

        # 任務二：三方審議與交叉評分 (GPT-5.2-Pro 主導)
        review_task = Task(
            description="審閱初稿，指出盲點，給予毒舌修正建議並進行 1-10 分邏輯評分。",
            expected_output="包含批判建議與專家評分的審閱報告。",
            agent=self.risk_critic,
            context=[research_task]
        )

        # 任務三：最終彙整定稿 (Gemini 整合)
        final_report_task = Task(
            description=dedent("""
                根據意見修正，產出 [Q-Silicon Institutional Research] Daily Brief。
                必須包含：
                1. 【📊 Market Dashboard】視覺指標。
                2. 【Q-Silicon Peer Review】包含來自 GPT-5.2-Pro 的專家評分與討論區塊。
            """),
            expected_output="一份具備討論深度、視覺指標且無情緒化的 Markdown 報告。",
            agent=self.quant_strategist,
            context=[research_task, review_task]
        )

        crew = Crew(
            agents=[self.macro_researcher, self.quant_strategist, self.risk_critic],
            tasks=[research_task, review_task, final_report_task], 
            process=Process.sequential
        )
        return crew.kickoff()

# ==========================================
# 三、 執行與發送邏輯
# ==========================================

if __name__ == "__main__":
    print("Initializing Q-Silicon Three-Agent Consensus System (Testing GPT-5.2-Pro)...")
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
        print("Telegram configuration missing.")
