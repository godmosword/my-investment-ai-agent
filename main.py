import os
from crewai import Agent, Task, Crew, Process
from textwrap import dedent

class QSiliconResearchCrew:
    def __init__(self):
        # 1. 多頭斥候：負責宏觀與新聞 (80% 淺顯概況)
        self.macro_researcher = Agent(
            role="華爾街首席市場研究員",
            goal="追蹤 DXY、美債殖利率變化，並過濾出 3 則具備邊際影響力的加密貨幣市場新聞。",
            backstory=dedent("""
                你是一名專精於跨資產連動的華爾街研究員。
                你的分析客觀冷靜，只描述『預期差』與『市場定價』，絕不使用情緒化字眼。
            """),
            llm="xai/grok-4-1-fast-reasoning",
            allow_delegation=False,
            verbose=True
        )

        # 2. 數據精算師：負責鏈上結構 (20% 高深分析)
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
            allow_delegation=False,
            verbose=True
        )

    def run(self):
        # 定義最終產出任務
        compile_report_task = Task(
            description=dedent("""
                請依據搜尋與擷取到的數據，撰寫一份 [Q-Silicon Institutional Research] Daily Brief。
                
                必須嚴格遵循以下 Markdown 結構：
                #### **一、 宏觀環境觀測 (Macro Sentiment)**
                (描述利率預期與跨資產連動)
                #### **二、 即時新聞摘要 (Market Catalysts)**
                (3則新聞及其對市場預期的傳導)
                #### **三、 鏈上結構分析 (On-chain Dynamics)**
                (深度解讀OI、流動性缺失與資金費率)
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
    # 啟動系統
    research_crew = QSiliconResearchCrew()
    final_report = research_crew.run()
    print("=== Q-Silicon Report Generated ===")
    print(final_report)
    # 這裡可以接續你原本的 Telegram 發送邏輯
