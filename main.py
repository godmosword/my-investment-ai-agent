import os
import requests
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from duckduckgo_search import DDGS
from datetime import datetime

# ================== 核心設定 ==================
TODAY = datetime.now().strftime("%Y/%m/%d")

# ================== LLM 大腦配置 ==================
grok_llm = LLM(model="xai/grok-4.20-beta", api_key=os.getenv("XAI_API_KEY"), temperature=0.7)
gemini_llm = LLM(model="gemini/gemini-3.1-pro", api_key=os.getenv("GEMINI_API_KEY"), temperature=0.2)

# ================== 數據工具 ==================
@tool("Market Intelligence Hub")
def market_data_tool(query: str = "") -> str:
    """獲取報價、恐懼貪婪、TVL 數據。"""
    try:
        p = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true").json()
        f = requests.get("https://api.alternative.me/fng/?limit=1").json()['data'][0]
        t = requests.get("https://api.llama.fi/v2/chains").json()
        eth_tvl = next((i for i in t if i["name"] == "Ethereum"), {}).get('tvl', 0) / 1e9
        return f"BTC: ${p['bitcoin']['usd']:,} | ETH: ${p['ethereum']['usd']:,} | F&G: {f['value']} | TVL: ${eth_tvl:.2f}B"
    except: return "數據異常"

# ================== 辯論特遣隊 ==================
# 1. 激進派：Grok
grok_agent = Agent(
    role="Aggressive Market Bull (Grok-4.2)",
    goal="從社群與即時新聞中找出市場最強勁的成長動力，說服老闆現在是買入或持有的好時機。",
    backstory="你是馬斯克式的科技信徒，對創新與波動充滿熱情。你擅長發現那些大眾尚未察覺的利多訊號。",
    tools=[market_data_tool],
    llm=grok_llm,
    verbose=True
)

# 2. 保守派：Gemini
gemini_agent = Agent(
    role="Conservative Risk Auditor (Gemini-3.1)",
    goal="挑戰 Grok 的觀點。利用鏈上數據與基本面，找出市場過熱、潛在風險或被忽略的利空訊息。",
    backstory="你是一位冷酷的精算師，不相信直覺，只相信數據與邏輯。你的任務是戳破任何泡沫化的幻想。",
    tools=[market_data_tool],
    llm=gemini_llm,
    verbose=True
)

# 3. 總編輯：整理者
editor_agent = Agent(
    role="Chief Financial Editor",
    goal="整理 Grok 與 Gemini 的辯論，產出一份具備對抗性思維的繁體中文日報。",
    backstory="你是一位理性的觀察者。你不會選邊站，而是把兩方的辯論精華提煉成『多空對決紀錄』與具體的建議。",
    llm=gemini_llm,
    verbose=True
)

# ================== 辯論任務流程 ==================
tasks = [
    Task(
        description="分析今日數據，提出 2 個當前市場最值得樂觀（Bullish）的關鍵點，語氣要強烈且具說服力。",
        agent=grok_agent,
        expected_output="激進派看多報告。"
    ),
    Task(
        description="針對 Grok 提出的看多觀點，進行嚴格的質疑與審查。列出至少 2 個潛在的崩盤風險或被隱藏的利空指標。",
        agent=gemini_agent,
        expected_output="保守派風險審查報告。"
    ),
    Task(
        description="""
        彙整上述兩方的辯論內容，寫成一份專業日報。格式如下：
        1. 📊 今日關鍵數據
        2. 🥊 多空對決：Grok 的樂觀觀點 vs. Gemini 的風險質疑
        3. 🛡️ 最終戰略行動建議 (針對穩定成長者的建議)
        4. 💡 總編碎碎念 (一句話總結今日市場 Vibe)
        使用繁體中文，格式需簡約且適合 Telegram 閱讀。
        """,
        agent=editor_agent,
        expected_output="最終 Telegram Markdown 日報。"
    )
]

# ================== 執行 ==================
if __name__ == "__main__":
    crew = Crew(agents=[grok_agent, gemini_agent, editor_agent], tasks=tasks, process="sequential")
    try:
        result = crew.kickoff()
        message = f"🥊 **{TODAY} ｜ 多空辯論透視**\n\n{result.raw}"
        requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                      json={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": message, "parse_mode": "Markdown"})
        print("✅ 辯論日報已發送！")
    except Exception as e: print(f"❌ 錯誤: {e}")
