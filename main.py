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
self.macro_researcher = Agent(
    role="華爾街首席市場研究員",
    goal="追蹤具有『市場爆點』的新聞敘事與全球宏觀數據變化。",
    backstory=dedent("""
        你具備敏銳的市場嗅覺。除了宏觀數據，你更擅長捕捉那些能引發市場情緒劇烈波動的『催化劑』。
        在搜集新聞時，優先尋找涉及：資金大遷徙、權力階層對話、以及能推動市場共識改變的事件。
        嚴禁提及台灣股市。
    """),
    llm="xai/grok-4-1-fast-reasoning",
    tools=[market_search_tool],
    verbose=True
)

self.quant_strategist = Agent(
    role="機構宏觀策略分析師",
    goal="將枯燥的鏈上數據轉化為視覺化的指標儀表板，並產出深度的 80/20 專業報告。",
    backstory=dedent("""
        你擅長將複雜的 CoinGlass 數據（如 OI、Funding Rate）提煉成讀者一眼就能看懂的『模擬線圖指標』。
        寫作要求：
        1. 在報告中加入『市場儀表板』區塊。
        2. 描述數據時要帶有『動態感』（例如：RSI 正在背離、爆倉牆正在向上平移）。
        3. 維持華爾街冷靜風格，但用更有張力的標題吸睛。
    """),
    llm="google/gemini-3.1-pro-preview",
    tools=[coinglass_data_tool],
    verbose=True
)

    def run(self):
        # 任務一：由 Grok 負責的宏觀與新聞偵察
        research_task = Task(
            description=dedent("""
                請使用 Tavily Market Search 工具，搜尋最新的全球宏觀經濟數據（如 DXY、美債殖利率變化）
                以及 3 則具備邊際影響力的數位資產市場新聞。
                請將結果整理成結構化的摘要，嚴禁包含任何台灣股市 (TAIEX) 的資訊。
            """),
            expected_output="包含最新宏觀數據與 3 則關鍵新聞的結構化摘要。",
            agent=self.macro_researcher
        )

        # 任務二：由 Gemini 負責抓取鏈上數據並最終定稿
        compile_report_task = Task(
            description=dedent("""
                請基於上一個任務(research_task)的研究摘要，並主動運用 CoinGlass 工具擷取最新鏈上數據，
                將所有資訊彙整成一份 [Q-Silicon Institutional Research] Daily Brief。
                架構：
                #### 一、 宏觀環境觀測 (Macro Sentiment)
                #### 二、 即時新聞摘要 (Market Catalysts)
                #### 三、 鏈上結構分析 (On-chain Dynamics)
                #### 四、 策略分析師備忘錄 (Executive Summary)
            """),
            expected_output="一份符合華爾街機構標準、不帶情緒且排版精確的 Markdown 報告。",
            agent=self.quant_strategist
        )

        # 將兩個任務放入陣列，確保 Grok 先跑，Gemini 接力
        crew = Crew(
            agents=[self.macro_researcher, self.quant_strategist],
            tasks=[research_task, compile_report_task], 
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
        bot = telebot.TeleBot(token)
        try:
            # 優先嘗試使用 Markdown 發送，維持精美排版
            bot.send_message(chat_id, final_report, parse_mode="Markdown")
            print("Report sent to Telegram successfully (Markdown format).")
        except Exception as e:
            print(f"Markdown parsing failed: {e}. Falling back to plain text.")
            try:
                # 若 Markdown 解析失敗，降級為純文字發送，確保你一定收得到戰報
                bot.send_message(chat_id, final_report)
                print("Report sent to Telegram successfully (Plain text format).")
            except Exception as e2:
                print(f"Critical failure in sending Telegram message: {e2}")
    else:
        print("Telegram configuration missing. Skipping broadcast.")
