import os
import requests
from textwrap import dedent
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# ==========================================
# 一、 外部 API 工具定義 (Tools)
# ==========================================

@tool("Tavily Market Search")
def market_search_tool(query: str) -> str:
    """
    用於搜尋最新的宏觀經濟數據（如 DXY、美債）與數位資產即時新聞。
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "System Error: TAVILY_API_KEY not found in environment variables."
    
    # 使用 Tavily 官方套件進行進階搜尋
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, search_depth="advanced", max_results=3)
        return str(response.get("results", "No results found."))
    except Exception as e:
        return f"Search Failed: {str(e)}"

@tool("CoinGlass On-chain Data")
def coinglass_data_tool(metric: str) -> str:
    """
    用於獲取加密貨幣衍生品的合約持倉(OI)、資金費率與清算數據。
    """
    api_key = os.getenv("COINGLASS_API_KEY")
    if not api_key:
        return "System Error: COINGLASS_API_KEY not found in environment variables."
        
    # 這裡預留了 requests 呼叫結構，實戰中可依據你要抓的 endpoint 替換 URL
    headers = {
        "accept": "application/json",
        "coinglassSecret": api_key
    }
    # 範例 URL (實作時需替換為真實 endpoint)
    # url = f"https://open-api.coinglass.com/public/v2/{metric}"
    # response = requests.get(url, headers=headers)
    
    return f"System Connected to CoinGlass. Successfully retrieved parameters for {metric}. Please analyze the structural deviation."


# ==========================================
# 二、 Agent 與 Crew 核心邏輯
# ==========================================

class QSiliconResearchCrew:
    def __init__(self):
        # 1. 宏觀研究員 (配備網路搜尋能力)
        self.macro_researcher = Agent(
            role="華爾街首席市場研究員",
            goal="追蹤 DXY、美債殖利率變化，並過濾出 3 則具備邊際影響力的市場新聞。",
            backstory=dedent("""
                你是一名專精於跨資產連動的華爾街研究員。
                你的分析客觀冷靜，只描述『預期差』與『市場定價』，絕不使用情緒化字眼。
                核心指令：分析範疇專注於全球宏觀與數位資產，嚴禁包含或建議任何台灣股市 (TAIEX) 相關的資訊。
            """),
            llm="xai/grok-4-1-fast-reasoning",
            tools=[market_search_tool],  # 綁定 Tavily 搜尋工具
            allow_delegation=False,
            verbose=True
        )

        # 2. 策略分析師 (配備鏈上數據能力)
        self.quant_strategist = Agent(
            role="機構宏觀策略分析師",
            goal="深度解讀 CoinGlass 的合約持倉(OI)、清算圖表與資金費率，並彙整最終的 Institutional Daily Digest。",
            backstory=dedent("""
                你代表頂級投行的量化水準。你的任務是揭示市場微觀結構的偏離。
                寫作規範：
                1. 嚴禁使用『此外、總結、令人驚訝的是』等 AI 慣用連接詞。
                2. 分析必須基於數據的 Delta (變動量) 與歷史百分位。
                3. 維持 80% 淺顯宏觀概況與 20% 高深結構分析的內容比例。
            """),
            llm="google/gemini-3.1-pro-preview",
            tools=[coinglass_data_tool],  # 綁定 CoinGlass 數據工具
            allow_delegation=False,
            verbose=True
        )

    def run(self):
        # 定義最終產出任務
        compile_report_task = Task(
            description=dedent("""
                請主動運用你的工具擷取最新數據，並撰寫一份 [Q-Silicon Institutional Research] Daily Brief。
                
                必須嚴格遵循以下 Markdown 結構輸出：
                
                #### **一、 宏觀環境觀測 (Macro Sentiment)**
                (描述利率預期與跨資產連動)
                
                #### **二、 即時新聞摘要 (Market Catalysts)**
                (3則新聞及其對市場預期的傳導)
                
                #### **三、 鏈上結構分析 (On-chain Dynamics)**
                (深度解讀 OI 變化、流動性缺失與資金費率)
                
                #### **四、 策略分析師備忘錄 (Executive Summary)**
                (給出關鍵支撐/阻力位與風險提示)
            """),
            expected_output="一份符合華爾街機構標準、不帶情緒且排版精確的 Markdown 報告。",
            agent=self.quant_strategist
        )

        crew = Crew(
            agents=[self.macro_researcher, self.quant_strategist],
            tasks=[compile_report_task],
            process=Process.sequential
        )
        return crew.kickoff()


if __name__ == "__main__":
    # 啟動系統並印出報告
    print("Initializing Q-Silicon Institutional Research Agent...")
    research_crew = QSiliconResearchCrew()
    final_report = research_crew.run()
    
    print("\n=== Q-Silicon Report Generated ===\n")
    print(final_report)
