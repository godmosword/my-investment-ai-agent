import os
import requests
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool  # 👈 改回從 crewai.tools 導入，這才是 standalone 腳本用的
from crewai_tools import TavilySearchTool
from datetime import datetime

# ================== 核心設定 ==================
TODAY = datetime.now().strftime("%Y/%m/%d")

# ================== 雙神獸 LLM 大腦配置 ==================
# Grok-beta: 負責最具侵略性的社群情緒與利多挖掘
grok_llm = LLM(
    model="xai/grok-beta", 
    api_key=os.getenv("XAI_API_KEY"),
    temperature=0.8
)

# Gemini 3.1 Pro: 負責數據精算、風險質疑與最終專業排版 (訂閱感核心)
gemini_llm = LLM(
    model="gemini/gemini-3.1-pro",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2
)

# ================== 專業數據工具箱 ==================
# 1. Tavily AI: 專為 AI 設計，抓取去雜訊的純淨財經新聞
search_tool = TavilySearchTool()

# 2. CoinGlass Intelligence: 監控全網爆倉數據與多空比
@tool
def coinglass_tool(query: str = "") -> str:
    """獲取全網 24H 爆倉數據與 BTC 多空比。"""
    key = os.getenv("COINGLASS_API_KEY")
    headers = {"accept": "application/json", "CG-API-KEY": key}
    try:
        liq_url = "https://open-api.coinglass.com/public/v2/liquidation_info"
        liq_res = requests.get(liq_url, headers=headers, timeout=10).json()
        total_liq = liq_res.get('data', [{}])[0].get('totalVolUsd', 'N/A')
        
        ls_url = "https://open-api.coinglass.com/public/v2/long_short?symbol=BTC&time_type=h24"
        ls_res = requests.get(ls_url, headers=headers, timeout=10).json()
        ls_ratio = ls_res.get('data', [{}])[0].get('longShortRatio', 'N/A')
        return f"【CoinGlass】24H 總爆倉: ${total_liq} | BTC 多空比: {ls_ratio}"
    except Exception as e:
        return f"數據連線異常: {str(e)}"

# 3. 基礎市場報價與恐懼貪婪指數
@tool
def price_tool(query: str = "") -> str:
    """獲取即時報價與恐懼貪婪指數。"""
    try:
        p = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true", timeout=10).json()
        f = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()['data'][0]
        return f"BTC: ${p['bitcoin']['usd']:,} ({p['bitcoin']['usd_24h_change']:.1f}%) | F&G Index: {f['value']} ({f['value_classification']})"
    except Exception as e:
        return f"報價異常: {str(e)}"

# ================== Agent 辯論陣容 ==================
bull_scout = Agent(
    role="Aggressive Market Bull (Grok-beta)",
    goal="發揮 X 平台資訊時效優勢，挖掘最強大的上漲理由，找出空頭即將被軋空的證據。",
    backstory="你是一位對科技與半導體充滿狂熱的分析師，深信數據背後隱藏著改變命運的機會。你講話風格犀利且具備侵略性。",
    tools=[search_tool, coinglass_tool, price_tool],
    llm=grok_llm,
    verbose=True
)

risk_auditor = Agent(
    role="Cold-Blooded Risk Assassin (Gemini-3.1)",
    goal="無情質疑 Grok 的觀點。利用爆倉數據與多空比，找出市場過熱與潛在的殺多訊號。",
    backstory="你是一位具備多年半導體產業經驗的資深精算師，冷靜、毒舌、不相信社群傳言。你的任務是守護投資人的本金。",
    tools=[search_tool, coinglass_tool, price_tool],
    llm=gemini_llm,
    verbose=True
)

# ================== 任務流程：打造訂閱感內容 ==================
tasks = [
    Task(
        description="分析最新數據與社群情緒，提出 2 個具備爆發力的看多觀點，並引用爆倉數據證明空頭回補的可能性。",
        agent=bull_scout,
        expected_output="充滿張力的看多分析。"
    ),
    Task(
        description="針對 Grok 的觀點進行數據打臉。找出多空比中潛在的風險，並提出一個足以毀滅倉位的極端預警。",
        agent=risk_auditor,
        expected_output="冷酷、精準的風險審查報告。"
    ),
   Task(
    description=f"""
    將上述辯論彙整為一份專業投資日報。
    
    【Qingpu Silicon Brain | 矽大腦戰報 - {TODAY}】
    
    1. 🔍 **核心數據看板**：
       - BTC 價格位階與 24H 漲跌。
       - 全網爆倉總量 (判斷目前是多頭被殺還是空頭被軋)。
    2. ⚔️ **專家針鋒相對**：
       - **Grok (激進派)**：基於 X 平台情緒，給出一個最瘋狂的買入理由。
       - **Gemini (理性派)**：基於 CoinGlass 數據，給出一個「讓你傾家蕩產」的風險警示。
    3. 💡 **小白投資策略**：將專業術語轉化為 30 秒能看完的行動清單。
    4. 🏛️ **產業洞察**：以半導體工程師視角，分析當前 AI 算力或宏觀趨勢對幣圈的影響。
    """,
    agent=risk_auditor,
    expected_output="一份精緻且具備極高商業價值的 Telegram Markdown 報告。"
)
]

# ================== 執行與發送 ==================
if __name__ == "__main__":
    crew = Crew(agents=[bull_scout, risk_auditor], tasks=tasks, process="sequential")
    try:
        result = crew.kickoff()
        message = f"🥊 **三位一體 ｜ 全能戰報**\n\n{result.raw}"
        
        # 修正 Markdown V2 潛在轉義問題，使用 Markdown 模式發送
        requests.post(
            f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", 
            json={
                "chat_id": os.getenv("TELEGRAM_CHAT_ID"), 
                "text": message, 
                "parse_mode": "Markdown"
            }
        )
        print("✅ 專業版戰報已發送！")
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
