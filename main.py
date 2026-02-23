import os
import requests
from crewai import Agent, Task, Crew, LLM, tool  # 👈 加上這個 tool 就能動了
from crewai_tools import TavilySearchTool  # 👈 修正後的正確導入名稱
from datetime import datetime

# ================== 核心設定 ==================
TODAY = datetime.now().strftime("%Y/%m/%d")

# ================== 雙神獸 LLM 大腦配置 ==================
# Grok-beta: 社群情緒與即時資訊的核心引擎
grok_llm = LLM(
    model="xai/grok-beta", 
    api_key=os.getenv("XAI_API_KEY"),
    temperature=0.8
)

# Gemini 3.1 Pro: 理性審核與專業報告總結
gemini_llm = LLM(
    model="gemini/gemini-3.1-pro",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2
)

# ================== 頂級數據工具箱 ==================
# 1. Tavily AI: 專為 AI 設計的高階搜尋引擎
# 我們開啟 'advanced' 模式，讓搜尋結果具備更深度的財經細節
search_tool = TavilySearchTool(search_depth="advanced") 

# 2. CoinGlass Intelligence: 監控爆倉與多空博弈
@tool("CoinGlass Data")
def coinglass_tool(query: str = "") -> str:
    """獲取全網 24H 爆倉數據與 BTC 多空比。"""
    key = os.getenv("COINGLASS_API_KEY")
    headers = {"accept": "application/json", "CG-API-KEY": key}
    try:
        liq_url = "https://open-api.coinglass.com/public/v2/liquidation_info"
        liq_res = requests.get(liq_url, headers=headers).json()
        total_liq = liq_res.get('data', [{}])[0].get('totalVolUsd', 'N/A')
        
        ls_url = "https://open-api.coinglass.com/public/v2/long_short?symbol=BTC&time_type=h24"
        ls_res = requests.get(ls_url, headers=headers).json()
        ls_ratio = ls_res.get('data', [{}])[0].get('longShortRatio', 'N/A')
        return f"【CoinGlass】24H 總爆倉: ${total_liq} | BTC 多空比: {ls_ratio}"
    except: return "CoinGlass API 連線異常"

# 3. 市場報價工具
@tool("Market Prices")
def price_tool(query: str = "") -> str:
    """獲取 BTC/ETH 價格與恐懼貪婪指數。"""
    try:
        p = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true").json()
        f = requests.get("https://api.alternative.me/fng/?limit=1").json()['data'][0]
        return f"BTC: ${p['bitcoin']['usd']:,} ({p['bitcoin']['usd_24h_change']:.1f}%) | F&G: {f['value']}"
    except: return "報價源異常"

# ================== 辯論 Agent 團隊 ==================
bull_scout = Agent(
    role="Aggressive Market Bull (Grok-beta)",
    goal="挖掘市場最強大的利多訊號，利用爆倉數據證明空頭即將崩潰。",
    backstory="你是一位狂熱的科技信徒，對 X 平台的趨勢有極強的預判能力。你只看機會，不看風險。",
    tools=[search_tool, coinglass_tool, price_tool],
    llm=grok_llm,
    verbose=True
)

risk_auditor = Agent(
    role="Cold-Blooded Risk Assassin (Gemini-3.1)",
    goal="無情質疑 Grok 的觀點。利用多空比與搜尋到的負面財經數據，找出潛在的災難性風險。",
    backstory="你是一位不帶感情的精算師。你的任務是戳破任何非理性的繁榮，確保報告絕對穩健。",
    tools=[search_tool, coinglass_tool, price_tool],
    llm=gemini_llm,
    verbose=True
)

# ================== 任務流程 ==================
tasks = [
    Task(
        description="收集今日數據並搜尋 2 條具全球影響力的利多新聞，提出極具侵略性的看多報告。",
        agent=bull_scout,
        expected_output="Grok 風格的看多報告。"
    ),
    Task(
        description="針對 Grok 的觀點進行針對性反駁。指出散戶過度槓桿與鏈上異常指標，提出風險預警。",
        agent=risk_auditor,
        expected_output="Gemini 風格的冷酷審查報告。"
    ),
    Task(
        description=f"""
        將上述辯論彙整為一份高品質的繁體中文 Markdown 報告。
        標題：【Grok-beta x CoinGlass x Tavily 聯名戰報 - {TODAY}】
        """,
        agent=risk_auditor,
        expected_output="最終 Telegram Markdown 日報內容。"
    )
]

# ================== 執行 ==================
if __name__ == "__main__":
    crew = Crew(agents=[bull_scout, risk_auditor], tasks=tasks, process="sequential")
    try:
        result = crew.kickoff()
        message = f"📬 **{TODAY} ｜ 多空戰報**\n\n{result.raw}"
        requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                      json={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": message, "parse_mode": "Markdown"})
        print("✅ 聯戰報告已送達！")
    except Exception as e: print(f"❌ 錯誤: {e}")
