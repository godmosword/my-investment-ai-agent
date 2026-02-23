import os
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from duckduckgo_search import DDGS
import requests
from datetime import datetime

# ================== 設定 ==================
WATCHLIST = ["BTC-USD", "ETH-USD"]
TODAY = datetime.now().strftime("%Y-%m-%d")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ================== LLM 大腦 ==================
gemini_llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.4 # 稍微調低創意度，減少日期幻覺
)

# ================== Tools (賦予員工新武器) ==================
@tool("DuckDuckGo Search")
def search_tool(query: str) -> str:
    """搜尋網路上的最新新聞與市場分析。關鍵字請加上 '2026' 與 '最新'。"""
    return str(DDGS().text(query, max_results=5))

@tool("CoinGecko Price API")
def crypto_price_tool(query: str = "") -> str:
    """獲取比特幣(BTC)和以太幣(ETH)的最精準即時價格與24小時漲跌幅。不需要傳入參數。"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
        response = requests.get(url, timeout=10).json()
        btc_p = response.get('bitcoin', {}).get('usd', 'N/A')
        btc_c = response.get('bitcoin', {}).get('usd_24h_change', 0)
        eth_p = response.get('ethereum', {}).get('usd', 'N/A')
        eth_c = response.get('ethereum', {}).get('usd_24h_change', 0)
        return f"【CoinGecko 權威即時報價】\nBTC: ${btc_p} (24h變化: {btc_c:.2f}%)\nETH: ${eth_p} (24h變化: {eth_c:.2f}%)"
    except Exception as e:
        return "報價API暫時無回應，請依賴搜尋引擎。"

# ================== Agents ==================
researcher = Agent(
    role="Senior Crypto Market Researcher",
    goal=f"使用 CoinGecko API 取得精確報價，並用搜尋引擎找出今日 ({TODAY}) 影響行情的具體新聞。",
    backstory="你是一個實戰派的情報員。比起完美的數據，你更在乎在現有資訊中挖掘出有價值的市場動態。不要抱怨工具，善用你手邊的資源。",
    tools=[search_tool, crypto_price_tool], # 👈 同時裝備搜尋和報價工具
    llm=gemini_llm,
    verbose=True
)

analyst = Agent(
    role="Crypto Investment Analyst",
    goal="根據情報給出具體的投資方向，不要寫免責聲明或拒絕分析。",
    backstory="你是實戰派分析師。就算資訊不完美，你也能憑藉經驗給出當下的判斷（買入/觀望/減持）、信心分數與具體風險。",
    llm=gemini_llm,
    verbose=True
)

reporter = Agent(
    role="Chief Report Writer",
    goal=f"寫一份清楚標示日期為 {TODAY} 的繁體中文報告，直接切入數據與分析，不要提及工具限制。",
    backstory="你最討厭廢話和藉口。你的報告總是單刀直入，排版乾淨，讓老闆一眼就能看出重點。",
    llm=gemini_llm,
    verbose=True
)

# ================== Tasks ==================
research_task = Task(
    description=f"1. 呼叫 CoinGecko API 獲取 {WATCHLIST} 最新價格。\n2. 搜尋今日重大新聞。列出 4 點具體的情報。",
    expected_output="包含準確價格與具體新聞的情報清單。",
    agent=researcher
)

analysis_task = Task(
    description="閱讀情報，強制給出具體的投資建議、信心分數，以及 2 個潛在風險。嚴禁輸出無法分析的理由。",
    expected_output="明確的建議、分數與風險。",
    agent=analyst
)

report_task = Task(
    description=f"統整資訊。確保報告標題日期為 {TODAY}。格式必須是 Markdown，包含：即時報價、市場動態、投資建議與風險。",
    expected_output="一份不包含任何推託之詞的專業繁體中文報告。",
    agent=reporter
)

# ================== Crew ==================
crew = Crew(
    agents=[researcher, analyst, reporter],
    tasks=[research_task, analysis_task, report_task],
    process="sequential",
    verbose=True,
    max_rpm=10
)

# ================== 執行 ==================
if __name__ == "__main__":
    try:
        result = crew.kickoff()
        report = result.raw
        
        # 強制加入防呆日期標頭
        message = f"👑 **加密貨幣快報 - {TODAY}**\n\n{report}"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, json=payload)
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")
