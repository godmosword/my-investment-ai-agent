import os
import requests
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from duckduckgo_search import DDGS
from datetime import datetime

# ================== 核心設定 ==================
TODAY = datetime.now().strftime("%Y/%m/%d")

# ================== 雙神獸 LLM 大腦 (火力全開配置) ==================
# Grok-4.1: 狂暴情報員，負責挖掘極限利多與社群瘋狂
grok_llm = LLM(
    model="xai/grok-4.1", 
    api_key=os.getenv("XAI_API_KEY"),
    temperature=0.8  # 高溫度讓觀點更犀利
)

# Gemini 3.1 Pro: 冷酷審核員，負責數據打臉與風險防禦
gemini_llm = LLM(
    model="gemini/gemini-3.1-pro",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1  # 極低溫度確保邏輯絕對嚴謹
)

# ================== 專業數據工具箱 ==================
@tool("Intense Market Data")
def market_data_tool(query: str = "") -> str:
    """獲取最精準的報價、情緒與鏈上 TVL 數據。"""
    try:
        p = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true").json()
        f = requests.get("https://api.alternative.me/fng/?limit=1").json()['data'][0]
        t = requests.get("https://api.llama.fi/v2/chains").json()
        eth_tvl = next((i for i in t if i["name"] == "Ethereum"), {}).get('tvl', 0) / 1e9
        return f"BTC: ${p['bitcoin']['usd']:,} | ETH: ${p['ethereum']['usd']:,} | F&G: {f['value']} | TVL: ${eth_tvl:.2f}B"
    except: return "數據傳輸中斷"

# ================== 辯論 Agent 陣容 ==================
bull_scout = Agent(
    role="Aggressive Crypto Bull (Grok-4.1)",
    goal="挖掘今日市場最強大的暴漲理由。你要用最激進、最不屑風險的口吻，說服所有人現在就是發財的機會。",
    backstory="你是一位混跡 X 平台、崇尚極速致富的科技狂熱者。你深信所有的利空都是大戶在洗盤，所有的風險都是怯懦者的藉口。",
    tools=[market_data_tool],
    llm=grok_llm,
    verbose=True
)

risk_auditor = Agent(
    role="Cold-Blooded Risk Assassin (Gemini-3.1)",
    goal="無情地拆穿 Grok 的幻想。利用鏈上數據找出被掩蓋的利空，給 Grok 的看多理由致命一擊。",
    backstory="你是一位在金融圈打滾三十年的冷面精算師。你最討厭情緒化的投資，你的任務是讓老闆在市場狂熱時保持清醒。",
    tools=[market_data_tool],
    llm=gemini_llm,
    verbose=True
)

# ================== 聯合作戰 Tasks ==================
tasks = [
    Task(
        description="分析最新數據，列出 2 個讓市場極度看好的『爆點』。語氣要狂妄，展現 Grok 4.1 的侵略性。",
        agent=bull_scout,
        expected_output="充滿張力的看多報告。"
    ),
    Task(
        description="針對 Grok 提出的觀點，每一點都要進行針對性的打臉反擊。引用鏈上數據證明現在的潛在危機，語氣要冷酷無情。",
        agent=risk_auditor,
        expected_output="毒舌且精準的風險審核報告。"
    ),
    Task(
        description=f"""
        將上述這場高強度的多空大戰整理成日報。
        格式要求：
        1. 📊 今日關鍵數據
        2. ⚔️ 多空生死戰 (Grok 的狂熱 vs Gemini 的冷水)
        3. 🛡️ 最終防禦策略 (給老闆的絕對安全指南)
        4. 💡 總編毒舌一句話 (點評這場辯論)
        
        標題：【Grok-4.1 x Gemini 聯名戰報 - {TODAY}】
        """,
        agent=risk_auditor, # 讓最理性的來寫最後總結
        expected_output="最終 Telegram Markdown 日報。"
    )
]

# ================== 啟動指令 ==================
if __name__ == "__main__":
    crew = Crew(agents=[bull_scout, risk_auditor], tasks=tasks, process="sequential")
    try:
        result = crew.kickoff()
        message = f"🥊 **火力全開版 ｜ 多空戰報**\n\n{result.raw}"
        requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                      json={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": message, "parse_mode": "Markdown"})
        print("✅ 戰報已發射！")
    except Exception as e: print(f"❌ 錯誤: {e}")
