import os
import requests
from crewai import Agent, Task, Crew, LLM
from crewai_tools import TavilySearchResultsTool
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

# Gemini 3.1 Pro: 負責數據精算、風險質疑與最終專業排版
gemini_llm = LLM(
    model="gemini/gemini-3.1-pro",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2
)

# ================== 頂級數據工具箱 ==================
# 1. Tavily AI: 比 DuckDuckGo 更精準、去雜訊的 AI 搜尋引擎
search_tool = TavilySearchResultsTool(api_key=os.getenv("TAVILY_API_KEY"))

# 2. CoinGlass Intelligence: 監控全網爆倉與多空比
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
    except: return "數據連線異常"

# 3. 基礎市場報價
@tool("Market Prices")
def price_tool(query: str = "") -> str:
    """獲取即時報價與恐懼貪婪指數。"""
    try:
        p = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true").json()
        f = requests.get("https://api.alternative.me/fng/?limit=1").json()['data'][0]
        return f"BTC: ${p['bitcoin']['usd']:,} ({p['bitcoin']['usd_24h_change']:.1f}%) | F&G Index: {f['value']}"
    except: return "報價異常"

# ================== Agent 辯論陣容 ==================
bull_scout = Agent(
    role="Aggressive Market Bull (Grok-beta Power)",
    goal="結合 X 平台動態與 Tavily 精準新聞，挖掘市場最強大的上漲理由，找出莊家正在布局的蛛絲馬跡。",
    backstory="你擁有馬斯克般的敏銳度。你深信所有的回調都是為了收割怯懦者，你只看見無限的機會與瘋狂的情緒。",
    tools=[search_tool, coinglass_tool, price_tool],
    llm=grok_llm,
    verbose=True
)

risk_auditor = Agent(
    role="Cold-Blooded Risk Assassin (Gemini-3.1 Power)",
    goal="針對 Grok 的觀點進行全方位的數據打臉。找出市場過熱、散戶過度槓桿與鏈上異常流出的風險點。",
    backstory="你是一位無情的精算師。你不相信社群傳言，只相信冷冰冰的爆倉數據與多空比。你的任務是預防災難性的爆倉。",
    tools=[search_tool, coinglass_tool, price_tool],
    llm=gemini_llm,
    verbose=True
)

# ================== 任務流程 ==================
tasks = [
    Task(
        description="分析最新數據與社群情緒，提出 2 個極具侵略性的看多觀點，並引用爆倉數據證明空頭即將被軋空。",
        agent=bull_scout,
        expected_output="充滿張力的看多報告。"
    ),
    Task(
        description="找出多空比中潛在的『殺多』訊號，針對 Grok 的觀點提出 2 個足以毀滅倉位的極端風險預警。",
        agent=risk_auditor,
        expected_output="精準、冷酷的風險審查報告。"
    ),
    Task(
        description=f"""
        將上述高強度的辯論彙整為一份高品質的繁體中文日報。
        1. 📊 今日核心看板 (含報價、情緒、爆倉量、多空比)
        2. ⚔️ 多空生死戰 (Grok 的狂熱 vs Gemini 的冷水)
        3. 🛡️ 戰略行動建議 (針對穩定成長者的建議)
        4. 💡 總編觀點 (一句話總結今日市場 Vibe)
        
        標題：【Grok-beta x CoinGlass x Tavily 聯名戰報 - {TODAY}】
        """,
        agent=risk_auditor,
        expected_output="最終 Telegram Markdown 專業戰報。"
    )
]

# ================== 執行與發送 ==================
if __name__ == "__main__":
    crew = Crew(agents=[bull_scout, risk_auditor], tasks=tasks, process="sequential")
    try:
        result = crew.kickoff()
        message = f"🥊 **三位一體 ｜ 全能戰報**\n\n{result.raw}"
        requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                      json={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": message, "parse_mode": "Markdown"})
        print("✅ 旗艦版戰報已發送！")
    except Exception as e: print(f"❌ 錯誤: {e}")
