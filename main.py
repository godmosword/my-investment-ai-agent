import os
import requests
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from duckduckgo_search import DDGS
from datetime import datetime

# ================== 核心設定 ==================
WATCHLIST = ["BTC-USD", "ETH-USD"]
TODAY = datetime.now().strftime("%Y-%m-%d")

# 💰 你的專屬持倉設定 (請根據真實狀況自由修改，AI 會根據這個給建議！)
MY_PORTFOLIO = """
目前持有部位：
1. BTC: 大約1.7顆，平均買入成本約 $55,000。
2. ETH: 大約37顆，平均買入成本約 $3,500。
3. 現金 (USDT/USDC): 佔總資金 <10%。
投資風格：穩健偏長線，但遇到極端行情願意使用合約對沖 (Hedge) 降低回撤風險。
"""

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ================== LLM 大腦 (頂配版) ==================
gemini_llm = LLM(
    model="gemini/gemini-3.1-pro", # 👈 你的最強大腦
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3 # 降低創意度，讓財務分析更嚴謹
)

# ================== 專業數據 Tools ==================
@tool("DuckDuckGo Search")
def search_tool(query: str) -> str:
    """搜尋網路上的最新新聞與市場分析。關鍵字請加上 '2026' 與 '最新'。"""
    return str(DDGS().text(query, max_results=3))

@tool("CoinGecko Price API")
def crypto_price_tool(query: str = "") -> str:
    """獲取 BTC 和 ETH 的最精準即時價格與 24 小時漲跌幅。"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
        response = requests.get(url, timeout=10).json()
        btc = response.get('bitcoin', {})
        eth = response.get('ethereum', {})
        return f"【報價】BTC: ${btc.get('usd', 'N/A')} ({btc.get('usd_24h_change', 0):.2f}%) | ETH: ${eth.get('usd', 'N/A')} ({eth.get('usd_24h_change', 0):.2f}%)"
    except:
        return "報價API無回應"

@tool("Fear and Greed Index API")
def fear_and_greed_tool(query: str = "") -> str:
    """獲取全網最新的恐懼與貪婪指數，判斷市場過熱或恐慌。"""
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
        data = res['data'][0]
        return f"【市場情緒】恐懼與貪婪指數: {data['value']} ({data['value_classification']})"
    except:
        return "情緒指數API無回應"

@tool("DefiLlama ETH TVL API")
def defillama_tool(query: str = "") -> str:
    """獲取以太坊鏈上總鎖倉量 (TVL)，判斷 ETH 基本面。"""
    try:
        res = requests.get("https://api.llama.fi/v2/chains", timeout=10).json()
        eth_data = next((item for item in res if item["name"] == "Ethereum"), None)
        if eth_data:
            tvl_billion = eth_data.get('tvl', 0) / 1e9
            return f"【鏈上數據】以太坊 TVL: 約 {tvl_billion:.2f} 十億美元"
        return "找不到 ETH TVL 數據"
    except:
        return "TVL API無回應"

# ================== 虛擬團隊 Agents ==================
researcher = Agent(
    role="Senior Crypto On-chain Researcher",
    goal="使用所有工具 (報價、情緒指數、TVL、搜尋)，描繪出今日市場的完整立體圖像。",
    backstory="你是一位精通鏈上數據與市場心理學的情報專家。你能輕易看出市場是否過熱，以及資金是否正在撤離以太坊。",
    tools=[search_tool, crypto_price_tool, fear_and_greed_tool, defillama_tool],
    llm=gemini_llm,
    verbose=True
)

analyst = Agent(
    role="Personal Wealth Manager & Risk Analyst",
    goal=f"根據情報，以及老闆的真實持倉 {MY_PORTFOLIO}，給出量身打造的部位管理建議。",
    backstory="你是老闆專屬的家族辦公室風險控管專家。如果市場極度貪婪，你會大膽建議對沖(Hedge)或套現；如果基本面良好且恐慌，你會建議用 USDT 抄底。絕不寫廢話。",
    llm=gemini_llm,
    verbose=True
)

reporter = Agent(
    role="Chief Report Writer",
    goal="將情報與持倉建議，濃縮成極具質感的 Markdown 日報。重點放在『下一步行動建議』。",
    backstory="你的排版乾淨俐落，善用條列式與粗體。能讓老闆在一分鐘內決定今天是要 HODL、開空單對沖、還是掛單買入。",
    llm=gemini_llm,
    verbose=True
)

# ================== 任務分配 Tasks ==================
research_task = Task(
    description="呼叫所有工具，取得今日 BTC/ETH 價格、恐懼貪婪指數、ETH TVL 數據，並搜尋 2 條重大新聞。",
    expected_output="包含所有數據與新聞重點的綜合情報包。",
    agent=researcher
)

analysis_task = Task(
    description=f"讀取情報與老闆的持倉配置：\n{MY_PORTFOLIO}\n計算浮盈/浮虧狀態，並給出明確建議：是否該 HODL、加倉、減倉，或建議具體的對沖策略 (例如：現貨不動，開 1 倍空單鎖定利潤)。",
    expected_output="針對老闆持倉的專屬分析與行動指導。",
    agent=analyst
)

report_task = Task(
    description=f"寫一份繁體中文報告，包含三個區塊：1. 📊 今日市場數據 (報價/情緒/鏈上) 2. 📰 重大動態 3. 🛡️ 專屬持倉建議與對沖策略。標題加上 {TODAY}。",
    expected_output="一份排版精美、直接給予操作建議的私人財富日報。",
    agent=reporter
)

# ================== Crew 執行 ==================
crew = Crew(
    agents=[researcher, analyst, reporter],
    tasks=[research_task, analysis_task, report_task],
    process="sequential",
    verbose=True
)

if __name__ == "__main__":
    try:
        result = crew.kickoff()
        report = result.raw
        
        message = f"👑 **專屬 AI 財富管家日報 - {TODAY}**\n\n{report}"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, json=payload)
        print("✅ 專屬日報已推送到 Telegram！")
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")
