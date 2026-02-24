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
    """搜尋全球宏觀數據與數位資產即時新聞。"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key: return "System Error: TAVILY_API_KEY not found."
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        # 加上 topic="news" 與 days=1，強制只抓取過去 24 小時內的新聞
        response = client.search(
            query=query, 
            search_depth="advanced", 
            max_results=5,
            topic="news",
            days=1
        )
        return str(response.get("results", "No results found."))
    except Exception as e: return f"Tavily Failed: {str(e)}"

@tool("X Real-time Trend Search")
def x_search_tool(query: str) -> str:
    """搜尋 X (Twitter) 上最新的加密貨幣討論情緒。"""
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
        "open_interest": "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d",
        "funding_rate": "https://open-api-v4.coinglass.com/api/futures/funding-rate/history?symbol=BTC&interval=1d",
        "liquidation": "https://open-api-v4.coinglass.com/api/futures/liquidation/aggregated-history?symbol=BTC&interval=1d"
    }
    url = endpoints.get(metric.lower(), endpoints["open_interest"])
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200: return str(response.json().get("data", []))[:2000]
        return f"CoinGlass Error: {response.status_code}"
    except Exception as e: return f"CoinGlass Failed: {str(e)}"

# ==========================================
# 二、 Agent 陣容：三核審議系統
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        # 1. 修改宏觀偵察兵 (加入嚴格時間要求)
        self.macro_researcher = Agent(
            role="華爾街首席市場研究員 (Spam-Filter Expert)",
            goal="搜尋並篩選出 3 則『過去 24 小時內』發生的高質量幣圈新聞，徹底避開舊新聞與 Spam。",
            backstory=dedent("""
                你使用 Grok-4-1，擁有最強的市場嗅覺。
                核心指令：
                1. 嚴格檢查新聞發布時間！如果新聞是超過 48 小時前的舊聞，立刻丟棄並重新搜尋。
                2. 搜尋時主動在關鍵字加上 "latest news", "today", 或 "past 24 hours"。
                3. 剔除重複標題、空洞廣告與台股內容。
            """),
            llm="xai/grok-4-1-fast-reasoning",
            tools=[market_search_tool, x_search_tool],
            verbose=True
        )

        # 2. 首席風控評論員 (GPT-4o)
        self.risk_critic = Agent(
            role="首席風險評論員 (Chief Risk Critic)",
            goal="針對新聞的真實性與市場風險進行『毒舌』審計，並給予評分。",
            backstory=dedent("""
                你使用 GPT-4o。你是華爾街的合夥人，負責質疑一切。
                你的短評必須直指要害：這則新聞是否只是市場噪音？是否隱含清算風險？
            """),
            llm="openai/gpt-4o",
            allow_delegation=True,
            verbose=True
        )

        # 3. 機構策略分析師 (Gemini 3.1)
        self.quant_strategist = Agent(
            role="機構宏觀策略分析師",
            goal="結合鏈上數據進行終極定稿，並製作視覺化 Dashboard。",
            backstory=dedent("""
                你使用 Gemini-3.1。你負責將前兩者的觀點與即時鏈上數據結合。
                你的短評將側重於數據層面的證實或證偽。
            """),
            llm="google/gemini-3.1-pro-preview",
            tools=[coinglass_data_tool],
            verbose=True
        )

    # 修正了這裡的縮排，確保 run 方法屬於 QSiliconResearchCrew 類別
    def run(self):
        # 任務一：偵查與情報獲取
        research_task = Task(
            description="抓取『過去 24 小時內』的宏觀數據與 3 則最新幣圈新聞。請在初稿中附上每則新聞的發布日期以供檢驗。必須過濾掉舊聞與垃圾資訊。",
            expected_output="包含 3 則『今日最新』新聞初稿與 Grok 短評的摘要。",
            agent=self.macro_researcher
        )

        # 任務二：風險審核
        review_task = Task(
            description="對 Grok 抓取的新聞進行風險評分，並提供你的獨立毒舌短評。",
            expected_output="包含評分與批判短評的備忘錄。",
            agent=self.risk_critic,
            context=[research_task]
        )

        # 任務三：最終彙整與報告產出
        final_report_task = Task(
            description=dedent("""
                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                
                【排版格式規範】：
                1. 📊 儀表板：使用 ASCII 進度條。
                2. 📰 即時熱點追蹤：每則新聞後必須排列以下『三核評選』區塊：
                   - 🛸 **Grok 觀點**: (短評)
                   - 🛡️ **GPT 評分**: (X/10 + 短評)
                   - 💎 **Gemini 洞察**: (數據短評)
                3. 維持四大標準結構與 80/20 比例。
            """),
            expected_output="具備視覺儀表板與 Agent 分開短評的專業報告。",
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
# 三、 執行與 Telegram 推送邏輯 (完整版)
# ==========================================

if __name__ == "__main__":
    print("Initializing Q-Silicon Agent...")
    research_crew = QSiliconResearchCrew()
    final_report = str(research_crew.run())
    
    print("\n=== Report Generated ===\n")
    print(final_report)
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        bot = telebot.TeleBot(token)
        try:
            # 優先嘗試使用 Markdown 發送
            bot.send_message(chat_id, final_report, parse_mode="Markdown")
            print("Telegram Push Success (Markdown).")
        except Exception as e:
            print(f"Markdown failed, falling back to Plain Text: {e}")
            try:
                # 降級為純文字發送，確保資訊不遺失
                bot.send_message(chat_id, final_report)
                print("Telegram Push Success (Plain Text).")
            except Exception as e2:
                print(f"Critical Failure: {e2}")
    else:
        print("Telegram configuration missing. Skipping push.")
