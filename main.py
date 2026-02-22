import os
import yfinance as yf
from crewai import Agent, Task, Crew, LLM
from crewai_tools import DuckDuckGoSearchTool
import requests
from datetime import datetime

# ================== 設定 ==================
WATCHLIST = ["2330.TW", "NVDA", "TSLA", "BTC-USD", "ETH-USD"]  # ← 想追的標的在這裡改
GEMINI_MODEL = "gemini/gemini-2.5-flash"   # 免費、快、強

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TODAY = datetime.now().strftime("%Y-%m-%d")

# ================== Gemini LLM ==================
gemini_llm = LLM(
    model=GEMINI_MODEL,
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

# ================== Tools ==================
search_tool = DuckDuckGoSearchTool()

# ================== Agents ==================
researcher = Agent(
    role="Senior Market Researcher",
    goal="只抓最新財報、財測、權威新聞，忽略社群噪音",
    backstory="你只相信官方數據與權威媒體",
    tools=[search_tool],
    llm=gemini_llm,
    verbose=True
)

analyst = Agent(
    role="Investment Analyst",
    goal="給出明確買/賣/持建議 + 信心分數 + 風險",
    backstory="你非常保守，只在多源一致時才建議買入",
    llm=gemini_llm,
    verbose=True
)

reporter = Agent(
    role="Report Writer",
    goal="用繁體中文寫 1 頁乾淨報告，Markdown 格式",
    backstory="你寫報告像華爾街日報一樣專業簡潔",
    llm=gemini_llm,
    verbose=True
)

# ================== Tasks ==================
research_task = Task(
    description=f"針對 {WATCHLIST} 收集最新數據：股價、財報重點、重大新聞、產業趨勢。只用可驗證來源。",
    expected_output="每檔標的 4-6 點 bullet points",
    agent=researcher
)

analysis_task = Task(
    description="根據研究結果，給出每檔標的的投資建議（強力買入/買入/持平/觀望/減持），附信心分數 0-100% 和主要風險。",
    expected_output="每檔標的：建議 + 信心% + 風險 3 點",
    agent=analyst
)

report_task = Task(
    description="把以上統整成一份繁體中文報告，標題含今日日期，結尾加『本報告由私人 AI Agent 產生，僅供參考』",
    expected_output="完整 Markdown 報告（不超過 800 字）",
    agent=reporter,
    output_file="daily_report.md"
)

# ================== Crew ==================
crew = Crew(
    agents=[researcher, analyst, reporter],
    tasks=[research_task, analysis_task, report_task],
    process="sequential",
    verbose=2
)

# ================== 執行 ==================
if __name__ == "__main__":
    print(f"🚀 {TODAY} 開始產生投資報告 (Gemini {GEMINI_MODEL})...")
    result = crew.kickoff()
    report = result.raw

    message = f"📈 **每日投資快報 - {TODAY}**\n\n{report}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("✅ 報告已推送到 Telegram！")
    else:
        print("⚠️ Telegram 推送失敗：", response.text)
