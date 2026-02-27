import os
import requests
import telebot
import logging
from urllib.parse import quote
from textwrap import dedent
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool, BaseTool
from google.cloud import bigquery  # 新增的 BigQuery 官方套件

# 載入環境變數
load_dotenv()

# 🚀 強制注入金鑰，確保 Google 原生 SDK 驗證通過
if os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# 一、 外部 API 工具定義 (含 AI 算力與宏觀指標)
# ==========================================

class BigQueryAnalyticsTool(BaseTool):
    # 重點：在變數名稱後加上 : str
    name: str = "BigQuery_Market_Data_Analyzer"
    description: str = "A tool to query Bitcoin whale transactions from BigQuery."

    def _run(self, query_type: str) -> str:
        try:
            # 初始化 BigQuery 客戶端，並帶入你專屬的專案 ID
            client = bigquery.Client(project="my-investment-ai-agent") 
            
            match query_type:
                case "crypto_whale_alert":
                    # 真實的 SQL 查詢範例 (需確保 GCP 上有這個資料集與資料表)
                    query = """
                        SELECT 
                            COUNT(*) as alert_count,
                            MAX(amount) as max_transfer
                        FROM `my-investment-ai-agent.market_data.btc_whale_transactions`
                        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
                        AND amount > 100
                    """
                    query_job = client.query(query)
                    results = query_job.result()
                    
                    for row in results:
                        return f'{{"status": "ok", "type": "crypto_whale_alert", "alert_count": {row.alert_count}, "max_transfer_btc": {row.max_transfer}}}'
                    return '{"status": "ok", "message": "No whale alerts in 24h"}'
                    
                case _:
                    return '{"status": "error", "message": "Unknown query type."}'
                    
        except Exception as e:
            return f'{{"status": "error", "message": "BigQuery Connection Failed: {str(e)}" }}'

@tool("AI Momentum Analyzer")
def ai_momentum_tool(metric: str) -> str:
    """獲取 AI 產業核心數據。metric 請輸入 'gpu_pricing' (H100/B200 租賃價) 或 'model_benchmarks' (排名)。"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key: return "TAVILY_API_KEY not found."
    from tavily import TavilyClient
    client = TavilyClient(api_key=api_key)
    
    queries = {
        "gpu_pricing": "current hourly rental price for NVIDIA H100 and B200 GPUs today",
        "model_benchmarks": "latest LMSYS Chatbot Arena ELO rankings for GPT-5, Claude 4, Gemini 3"
    }
    query = queries.get(metric.lower(), "latest AI compute economy")
    try:
        response = client.search(query=query, search_depth="advanced", max_results=3)
        return str(response.get("results", "No data found."))
    except Exception as e: 
        return f"AI Tool Failed: {str(e)}"

@tool("Macro Liquidity Tracker")
def macro_liquidity_tool(indicator: str) -> str:
    """獲取全球宏觀指標。indicator 請輸入 'M2' (貨幣供應), 'CPI' (通膨) 或 'DXY' (ICE 美指)。"""
    indicator_upper = indicator.upper()

    # 特別處理 DXY：改用 Tavily 搜尋 ICE US Dollar Index 即時報價
    if indicator_upper == "DXY":
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Macro Tracker Failed (Tavily)。TAVILY_API_KEY 未設定，無法查詢 ICE DXY。"
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            res = client.search(
                query="current ICE US Dollar Index (DXY) real-time quote today",
                search_depth="basic",
                max_results=3,
            )
            return str(res.get("results", "ICE DXY data not found."))
        except Exception as e:
            return f"Macro Tracker Failed (Tavily ICE DXY)。請檢查 TAVILY_API_KEY 或網路連線。詳細錯誤：{str(e)}"

    # 其餘指標 (M2 / CPI) 走 FRED API
    fred_key = os.getenv("FRED_API_KEY")
    if not fred_key:
        return "Macro Tracker Failed (FRED)。FRED_API_KEY 未設定，無法查詢 M2 / CPI。"

    series_map = {"M2": "M2SL", "CPI": "CPIAUCSL"}
    series_id = series_map.get(indicator_upper)
    if not series_id:
        return f"Macro Tracker Failed (FRED)。不支援的指標：{indicator}，僅支援 M2 與 CPI。"

    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_key}&file_type=json&sort_order=desc&limit=1"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 403:
            return "Macro Tracker Failed (FRED 403)。可能是 FRED_API_KEY 無效或權限不足。"
        if response.status_code == 429:
            return "Macro Tracker Failed (FRED 429)。FRED API 流量超限，請稍後再試。"
        response.raise_for_status()
        latest = response.json().get("observations", [{}])[0]
        return f"{indicator_upper}: {latest.get('value')} (Date: {latest.get('date')})"
    except Exception as e:
        return f"Macro Tracker Failed (FRED)。請檢查 FRED_API_KEY、網路連線或 API 狀態。詳細錯誤：{str(e)}"

@tool("Tavily Market Search")
def market_search_tool(query: str) -> str:
    """搜尋全球即時新聞。"""
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, search_depth="advanced", max_results=5, topic="news", days=1)
        return str(response.get("results", []))
    except Exception as e:
        return f"Market Search Failed: {str(e)}"

@tool("X Real-time Trend Search")
def x_search_tool(query: str) -> str:
    """搜尋 X 情緒。"""
    try:
        bearer_token = os.getenv("X_BEARER_TOKEN")
        url = f"https://api.twitter.com/2/tweets/search/recent?query={quote(query)}&max_results=10"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        tweets = response.json().get("data", [])
        return "\n".join([f"- {t['text']}" for t in tweets]) if tweets else "No tweets found."
    except Exception as e:
        return f"X Search Failed: {str(e)}"

@tool("CoinGlass On-chain Data")
def coinglass_data_tool(metric: str) -> str:
    """獲取幣圈衍生品數據。"""
    try:
        api_key = os.getenv("COINGLASS_API_KEY")
        headers = {"accept": "application/json", "coinglassSecret": api_key}
        url = "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return str(response.json().get("data", []))[:2000]
    except Exception as e:
        return f"CoinGlass Tool Failed: {str(e)}"

@tool("CryptoQuant On-chain Data")
def cryptoquant_tool(indicator: str) -> str:
    """獲取交易所流入數據。"""
    try:
        api_key = os.getenv("CRYPTOQUANT_API_KEY")
        url = "https://api.cryptoquant.com/v1/btc/exchange-flows/inflow?limit=1"
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get("result", {}).get("data", [])
        return f"BTC Inflow: {data[0].get('inflow')} BTC" if data else "No data."
    except Exception as e:
        return f"CryptoQuant Tool Failed: {str(e)}"


@tool("Rumor & Controversy Scanner")
def rumor_scanner_tool(topic: str) -> str:
    """
    掃描圍繞指定主題的爭議、調查報導與未證實傳聞，只使用公開資訊來源。
    嚴格標註「傳聞性質 / 可信度」，僅供風險研究與情緒監控使用，不構成投資建議或事實認定。
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "TAVILY_API_KEY not found."

    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)

    # 加強偏向「爭議 / 風險」的搜尋語意，但同時要求來源與可信度評估
    query = (
        f"recent controversies, investigations, lawsuits, market manipulation accusations, "
        f"security incidents, model leaks, whistleblower reports related to {topic}. "
        "Return only publicly reported information from credible sources. "
        "For each item, clearly state if it is: confirmed, likely, or unverified rumor."
    )

    try:
        result = client.search(
            query=query,
            search_depth="advanced",
            max_results=8,
            topic="news",
            days=30,
        )
        return str(result.get("results", []))
    except Exception as e:
        return f"Rumor Scanner Failed: {str(e)}"

# ==========================================
# 二、 Agent 陣容：嚴格鎖定指定模型 (修正 OpenAI 對話通道)
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        
        # 🛸 Grok
        grok_latest = LLM(model="xai/grok-4-1-fast-reasoning", api_key=os.getenv("XAI_API_KEY"))
        # 🤖 GPT
        gpt_latest = LLM(model="openai/gpt-5.2-chat-latest", api_key=os.getenv("OPENAI_API_KEY"))
        # 🛡️ Claude
        claude_latest = LLM(model="openrouter/anthropic/claude-sonnet-4.6", api_key=os.getenv("OPENROUTER_API_KEY"))
        # 💎 Gemini
        gemini_latest = LLM(model="gemini/gemini-3.1-pro-preview", api_key=os.getenv("GEMINI_API_KEY"))

        # 實例化 BigQuery 工具
        self.bq_tool = BigQueryAnalyticsTool()

        self.crypto_researcher = Agent(
            role="幣圈與宏觀市場研究員",
            goal="挑選 5 則幣圈新聞並分析宏觀 M2/DXY 指標，同時標記潛在『未證實市場傳聞』與操盤爭議。",
            backstory="您擅長交叉比對鏈上流向、全球流動性與市場敘事，特別留意具殺傷力的負面訊號，但嚴格區分事實與傳聞。",
            llm=grok_latest, 
            # BigQuery + 市場新聞 + X 情緒 + Rumor 掃描
            tools=[market_search_tool, x_search_tool, macro_liquidity_tool, self.bq_tool, rumor_scanner_tool],
            verbose=True
        )

        self.ai_researcher = Agent(
            role="前沿 AI 科技研究員",
            goal="挑選 5 則最新 AI 動態並分析 GPU 租賃成本與模型性能排名，特別追蹤模型洩漏、數據濫用與安全爭議。",
            backstory="您關注矽谷與全球 AI 生態的黑暗面，包含模型洩漏、算力壟斷與安全事故，同時會標明可信度與風險等級。",
            llm=gpt_latest, 
            tools=[market_search_tool, x_search_tool, ai_momentum_tool, rumor_scanner_tool],
            verbose=True
        )

        self.risk_critic = Agent(
            role="首席風險與邏輯評論員",
            goal="針對數據與『八卦 / 傳聞』進行毒舌審計，區分可驗證事實與純敘事炒作，並標註風險等級。",
            backstory="您負責潑冷水，揭露虛假的指標背離與敘事操縱，特別審視所謂內線或八卦是否有足夠證據支撐。",
            llm=claude_latest, 
            allow_delegation=False,
            verbose=True
        )

        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="整合『精準數據儀表板』與 Agent 短評。Gemini 是您的靈魂。",
            backstory="您負責最後排版，嚴禁廢話。僅列出有實際參與評述的 Agent。",
            llm=gemini_latest, 
            tools=[coinglass_data_tool, cryptoquant_tool],
            verbose=True
        )

    def run(self):
        crypto_task = Task(
            description=dedent("""
                【幣圈「八卦與內線」情報網任務——請嚴格依照以下指示行動】

                1. 必須呼叫 macro_liquidity_tool，獲取「最新 DXY 指標」與說明其變動方向，僅使用公開數據。
                2. 必須呼叫 BigQuery 工具（BigQuery_Market_Data_Analyzer），以 query_type="crypto_whale_alert" 取得過去 24 小時的巨鯨交易統計。
                3. 必須呼叫 rumor_scanner_tool 與 market_search_tool，搜尋以下關鍵字（僅限公開新聞 / 報導來源）：
                   'crypto market maker manipulation OR Jane Street rumor OR BTC ETF flow leak'
                4. 必須呼叫 x_search_tool，搜尋 X 上的關鍵字：
                   'crypto rumor OR BTC leak OR whale manipulation'

                【強制輸出規範（極為嚴格，請逐條遵守）】：
                - 僅使用可公開取得的新聞與社群內容，不得捏造任何「未出現於來源中的」具體事實或人物指控。
                - 必須明確列出「5 則具爭議性或前瞻性」的市場新聞，內容需與：
                  做市商行為、槓桿清算風險、ETF 資金流、巨鯨行為或 Jane Street 類型機構操作「傳聞」相關。
                - 對每一則新聞，需標註：
                  (a) 資訊來源（例如：媒體 / 報告 / 研究機構）
                  (b) 性質：confirmed / likely / unverified rumor（三選一）
                  (c) 您的風險與可信度評論。
                - 必須原汁原味列出「3 則最具殺傷力的 X 原始推文內容」，並對每則推文加上：
                  (a) 該推文的具體主張
                  (b) 您對其可信度的評估
                  (c) 若為純情緒帶風向，請明確指出。
                - 對於每一則新聞與推文，請額外給出統一格式的標籤行：
                  【RISK_SCORE】x/5｜【NARRATIVE】FOMO/FUD/Infra/Regulation/Other｜【HORIZON】intraday/swing/cycle

                嚴禁輸出任何法律建議或保證某傳聞為真。所有內容必須標註為「市場敘事 / 傳聞」，僅供風險研究與情緒監控使用。
            """),
            expected_output="一份包含：最新 DXY 指標解讀、BigQuery 巨鯨警報摘要、5 則具爭議性的幣圈新聞（附來源與可信度標註），以及 3 則最具殺傷力 X 推文與 Grok 的辛辣評論與風險評分的完整初稿。",
            agent=self.crypto_researcher
        )

        ai_task = Task(
            description=dedent("""
                【AI 圈「黑暗傳聞」情資任務——請嚴格依照以下指示行動】

                1. 必須獲取最新 H100/B200 價格或 LMSYS 模型排名，可透過 ai_momentum_tool 或 Tavily 等工具，不得捏造指標數值。
                2. 必須呼叫 rumor_scanner_tool 與 market_search_tool，搜尋以下關鍵字（僅限公開新聞 / 報導來源）：
                   'AI model leak OR OpenAI internal drama OR NVIDIA secret project'
                3. 必須呼叫 x_search_tool，搜尋 X 上的關鍵字：
                   '#OpenSourceAI breakthrough OR AI rumor OR Sam Altman drama'

                【強制輸出規範（極為嚴格，請逐條遵守）】：
                - 僅使用可公開取得的新聞、部落格與開發者社群內容，不得捏造「從未出現在來源中的」內線或機密資訊。
                - 必須明確列出「5 則矽谷暗盤或未正式對外公關包裝的 AI 產業動態」，例如：
                  模型洩漏事件、內部文化與管理爭議、GPU 供應與算力壟斷爭議、開源社群爆料等。
                - 對每一則動態，需標註：
                  (a) 資訊來源（開發者論壇、技術部落格、主流媒體等）
                  (b) 性質：confirmed / likely / unverified rumor
                  (c) 您對其對產業格局與投資情緒之潛在影響。
                - 必須原汁原味列出「3 則來自開發者社群的 X 原始推文內容」，並對每則推文加上：
                  (a) 具體技術或內部狀況主張
                  (b) 您對其專業度與可信度的評估
                  (c) 是否可能被誇大、帶有個人情緒或商業動機。
                - 對於每一則新聞與推文，請額外給出統一格式的標籤行：
                  【RISK_SCORE】x/5｜【NARRATIVE】FOMO/FUD/Infra/Regulation/Other｜【HORIZON】intraday/swing/cycle

                嚴禁聲稱掌握真實內線或未公開機密；所有內容均須標註為「產業傳聞與社群敘事」，僅供風險研究與前瞻情緒分析使用。
            """),
            expected_output="一份包含：最新 H100/B200 價格或 LMSYS 排名摘要、5 則具爭議性的 AI 產業傳聞與動態（附來源與可信度標註），以及 3 則來自開發者社群的代表性 X 推文與 GPT 的辛辣評論與產業風險評估的完整初稿。",
            agent=self.ai_researcher
        )

        review_task = Task(
            description=dedent("""
                綜合幣圈與 AI 區塊的所有數據與傳聞，執行以下任務：
                1. 審查各指標與新聞、推文的一致性與可信度，指出明顯誇大或自相矛盾之處。
                2. 對每一類主要敘事（例如：ETF 資金流、巨鯨操盤、模型洩漏、算力壟斷）給出「風險說明」與「可能被市場過度/不足定價」的簡短評語。
                3. 給出當前市場的整體模式標籤 (market_regime)，只能從下列三者中擇一：
                   - risk_on
                   - risk_off
                   - neutral
                   並用不超過 3 個關鍵驅動因子說明理由（例如：DXY 走強 + OI 降溫 + FUD 類傳聞升溫）。
            """),
            expected_output="一份包含：各主要敘事的可信度與風險批註、以及最終 market_regime（risk_on / risk_off / neutral）與 3 個關鍵驅動因子的審計備忘錄。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        final_report_task = Task(
            description=dedent("""
                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                
                【儀表板區塊】：
                - AI 算力價格/排名
                - 宏觀流動性 (M2/DXY)
                - 幣圈鏈上與巨鯨警報 (OI/Inflow/Whale)
                
                【開頭總結區塊】：
                - 先明確給出「今日市場模式 (market_regime)」：risk_on / risk_off / neutral（三選一）。
                - 緊接著列出 3 個最關鍵的驅動因子，簡短說明為何形成這個模式（可引用風險審計備忘錄中的結論）。
                
                【內容排版規則 - 必須嚴格遵守】：
                1. 幣圈區塊：
                   - 必須先列出 Grok 找到的「5 則爭議新聞」與「3 則 X (Twitter) 原始推文」。
                   - 接著再顯示 🛸 **Grok**、🛡️ **Claude** 與 💎 **主編** 的評論。
                2. AI 區塊：
                   - 必須先列出 GPT 找到的「5 則暗盤新聞」與「3 則 X (Twitter) 原始推文」。
                   - 接著再顯示 🤖 **GPT**、🛡️ **Claude** 與 💎 **主編** 的評論。
                
                🚨 嚴禁主編(Gemini)私自刪減新聞標題與推文原文！保留原始內容！
            """),
            expected_output="Telegram 最佳化、同時完整保留 Grok/GPT 所提供的 5 則新聞與 3 則 X 推文原文，並附上各 Agent 評論與風險標註的專業戰報。",
            agent=self.quant_strategist,
            context=[crypto_task, ai_task, review_task]
        )

        crew = Crew(
            agents=[self.crypto_researcher, self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[crypto_task, ai_task, review_task, final_report_task], 
            process=Process.sequential
        )
        return crew.kickoff()

# ==========================================
# 三、 執行與 Telegram 推送邏輯
# ==========================================

if __name__ == "__main__":
    logging.info("Initializing Q-Silicon Ultimate Agent...")
    
    try:
        research_crew = QSiliconResearchCrew()
        final_report = str(research_crew.run())
        logging.info("Report Generation Successful.")
    except Exception as e:
        final_report = f"🚨 Q-Silicon 智庫執行失敗，請檢查系統日誌。\n錯誤訊息：{str(e)}"
        logging.error(f"Execution Failed: {e}")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        bot = telebot.TeleBot(token)
        chunks = [final_report[i:i+4000] for i in range(0, len(final_report), 4000)]
        for chunk in chunks:
            try:
                bot.send_message(chat_id, chunk, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Telegram Message Failed: {e}")
                bot.send_message(chat_id, chunk)
    else:
        logging.warning("Telegram configuration missing. Skipping push.")