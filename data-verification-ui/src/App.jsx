import { useState } from "react";

const steps = [
  {
    id: 1,
    phase: "初步掃描",
    icon: "👁",
    color: "#4FACFE",
    humanAnalogy: "人類拿到數據的第一眼",
    checks: [
      { label: "欄位是否齊全？", type: "structure" },
      { label: "數量是否合理？（不能太多或太少）", type: "structure" },
      { label: "有沒有明顯空白或亂碼？", type: "structure" },
    ],
    code: `def scan_structure(data):
    required_fields = ["id", "name", "price", "date"]
    missing = [f for f in required_fields if f not in data]
    
    if missing:
        return {"pass": False, "reason": f"缺少欄位: {missing}"}
    if len(data) == 0:
        return {"pass": False, "reason": "數據為空"}
    
    return {"pass": True}`,
    outcome: "pass",
  },
  {
    id: 2,
    phase: "數值直覺",
    icon: "🔢",
    color: "#43E97B",
    humanAnalogy: "有沒有「看起來就不對」的數字",
    checks: [
      { label: "數字範圍符合常識嗎？", type: "value" },
      { label: "有沒有負數、零值異常？", type: "value" },
      { label: "日期是否在合理區間？", type: "value" },
    ],
    code: `def value_intuition(data):
    anomalies = []
    
    for item in data:
        # 價格不可能是負數或超過百萬
        if not (0 < item["price"] < 1_000_000):
            anomalies.append(f"價格異常: {item['price']}")
        
        # 日期不能是未來時間
        if item["date"] > today():
            anomalies.append(f"未來日期: {item['date']}")
    
    return {"pass": len(anomalies)==0, "anomalies": anomalies}`,
    outcome: "flag",
  },
  {
    id: 3,
    phase: "邏輯一致性",
    icon: "🔗",
    color: "#FA709A",
    humanAnalogy: "前後數據有沒有互相矛盾",
    checks: [
      { label: "總計 = 各項加總？", type: "logic" },
      { label: "狀態與數值一致？（已售出但庫存>0）", type: "logic" },
      { label: "關聯欄位互相對應？", type: "logic" },
    ],
    code: `def logic_consistency(data):
    errors = []
    
    for item in data:
        # 訂單總額應等於單價 × 數量
        expected = item["unit_price"] * item["qty"]
        if abs(item["total"] - expected) > 0.01:
            errors.append(
                f"總額不符: {item['total']} ≠ {expected}"
            )
        
        # 已完成訂單不能有未付款狀態
        if item["status"]=="完成" and item["payment"]=="未付":
            errors.append(f"狀態矛盾: {item['id']}")
    
    return {"pass": len(errors)==0, "errors": errors}`,
    outcome: "pass",
  },
  {
    id: 4,
    phase: "與來源比對",
    icon: "📋",
    color: "#F7971E",
    humanAnalogy: "回頭核對原始文件或資料庫",
    checks: [
      { label: "關鍵數字與原始來源一致？", type: "source" },
      { label: "AI 有沒有自行補填數據？", type: "source" },
      { label: "抽樣 10% 做人工確認", type: "source" },
    ],
    code: `def source_verification(ai_data, source_data, sample_rate=0.1):
    import random
    
    # 抽樣比對
    sample = random.sample(ai_data, 
                           int(len(ai_data) * sample_rate))
    mismatches = []
    
    for item in sample:
        original = source_data.get(item["id"])
        if not original:
            mismatches.append(f"來源找不到: {item['id']}")
            continue
        
        # 關鍵欄位必須完全一致
        for field in ["price", "name"]:
            if item[field] != original[field]:
                mismatches.append(
                    f"[{item['id']}] {field} 不符: "
                    f"AI={item[field]}, 原始={original[field]}"
                )
    
    return {"pass": len(mismatches)==0, "detail": mismatches}`,
    outcome: "pass",
  },
  {
    id: 5,
    phase: "AI 自我審查",
    icon: "🤖",
    color: "#A18CD1",
    humanAnalogy: "讓第二個 AI 扮演審查員",
    checks: [
      { label: "第二個 AI call 重新驗證", type: "ai" },
      { label: "要求 AI 解釋每個數字的來源", type: "ai" },
      { label: "信心分數 < 0.8 的項目標記", type: "ai" },
    ],
    code: `def ai_self_audit(data, source_text):
    prompt = f"""
你是數據審查員。請逐一檢查以下提取的數據
是否與原始文件一致，並給出信心分數 0-1。

提取結果：
{json.dumps(data, ensure_ascii=False)}

原始文件：
{source_text}

回傳格式：
{{
  "items": [
    {{"id": "...", "confidence": 0.95, "note": "..."}}
  ],
  "overall_pass": true
}}
"""
    result = call_claude(prompt)
    
    # 標記低信心項目
    low_conf = [x for x in result["items"] 
                if x["confidence"] < 0.8]
    return {"flagged": low_conf, **result}`,
    outcome: "flag",
  },
  {
    id: 6,
    phase: "最終裁決",
    icon: "⚖️",
    color: "#30CFD0",
    humanAnalogy: "綜合所有結果，決定放行或退回",
    checks: [
      { label: "所有關卡都通過 → 自動放行", type: "final" },
      { label: "有 flag 但無 error → 人工複核", type: "final" },
      { label: "有 error → 退回重新提取", type: "final" },
    ],
    code: `def final_verdict(results):
    has_error  = any(not r["pass"] for r in results)
    has_flag   = any(r.get("flag") for r in results)
    
    if has_error:
        return {
            "action": "REJECT",
            "label": "❌ 退回重新提取",
            "reason": [r["reason"] for r in results 
                       if not r["pass"]]
        }
    elif has_flag:
        return {
            "action": "REVIEW",
            "label": "⚠️ 送人工複核",
            "items": [r["flagged"] for r in results 
                      if r.get("flag")]
        }
    else:
        return {
            "action": "APPROVE",
            "label": "✅ 自動放行",
        }`,
    outcome: "approve",
  },
];

const outcomeColors = {
  pass: { bg: "#0d2b1a", border: "#22c55e", text: "#4ade80", label: "✓ PASS" },
  flag: { bg: "#2b1f0a", border: "#f59e0b", text: "#fbbf24", label: "⚠ FLAG" },
  approve: { bg: "#0d1f2b", border: "#38bdf8", text: "#7dd3fc", label: "→ 放行" },
};

export default function App() {
  const [activeStep, setActiveStep] = useState(null);
  const [showCode, setShowCode] = useState({});

  const toggleCode = (id, e) => {
    e.stopPropagation();
    setShowCode((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#080c14",
      fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      color: "#c9d1d9",
      padding: "40px 24px",
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 56 }}>
        <div style={{
          display: "inline-block",
          background: "linear-gradient(135deg, #1a2332, #0f1923)",
          border: "1px solid #1e3a5f",
          borderRadius: 4,
          padding: "4px 16px",
          fontSize: 11,
          letterSpacing: 4,
          color: "#4FACFE",
          marginBottom: 16,
          textTransform: "uppercase",
        }}>
          DATA VERIFICATION SYSTEM v2.1
        </div>
        <h1 style={{
          fontSize: "clamp(24px, 4vw, 40px)",
          fontWeight: 800,
          letterSpacing: -1,
          margin: "0 0 8px",
          background: "linear-gradient(90deg, #e6edf3, #8b949e)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}>
          模擬人類審核的 AI 數據驗證流程
        </h1>
        <p style={{ color: "#6e7681", fontSize: 14, margin: 0 }}>
          點擊每個階段查看詳細邏輯與程式碼實作
        </p>
      </div>

      {/* Flow */}
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        {steps.map((step, idx) => {
          const isActive = activeStep === step.id;
          const oc = outcomeColors[step.outcome];

          return (
            <div key={step.id}>
              {/* Step Card */}
              <div
                onClick={() => setActiveStep(isActive ? null : step.id)}
                style={{
                  background: isActive
                    ? "linear-gradient(135deg, #0d1b2a, #111d2e)"
                    : "#0d1117",
                  border: `1px solid ${isActive ? step.color + "60" : "#1e2a3a"}`,
                  borderLeft: `3px solid ${step.color}`,
                  borderRadius: 8,
                  padding: "20px 24px",
                  cursor: "pointer",
                  transition: "all 0.2s",
                  boxShadow: isActive ? `0 0 30px ${step.color}15` : "none",
                }}
              >
                {/* Top Row */}
                <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 24 }}>{step.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <span style={{
                        fontSize: 11, letterSpacing: 2,
                        color: step.color, opacity: 0.7,
                      }}>
                        STAGE {step.id.toString().padStart(2, "0")}
                      </span>
                      <span style={{
                        fontSize: 18, fontWeight: 700,
                        color: "#e6edf3", letterSpacing: -0.5,
                      }}>
                        {step.phase}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "#6e7681", marginTop: 2 }}>
                      💭 {step.humanAnalogy}
                    </div>
                  </div>
                  <div style={{
                    padding: "4px 12px",
                    background: oc.bg,
                    border: `1px solid ${oc.border}40`,
                    borderRadius: 4,
                    fontSize: 12,
                    color: oc.text,
                    fontWeight: 600,
                  }}>
                    {oc.label}
                  </div>
                  <div style={{ color: "#444d56", fontSize: 12 }}>
                    {isActive ? "▲" : "▼"}
                  </div>
                </div>

                {/* Expanded Content */}
                {isActive && (
                  <div style={{ marginTop: 24 }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                      {/* Checklist */}
                      <div>
                        <div style={{
                          fontSize: 10, letterSpacing: 3,
                          color: "#4e5a65", marginBottom: 12,
                          textTransform: "uppercase",
                        }}>
                          檢查清單
                        </div>
                        {step.checks.map((c, i) => (
                          <div key={i} style={{
                            display: "flex", alignItems: "flex-start",
                            gap: 10, marginBottom: 10,
                            padding: "10px 14px",
                            background: "#0a0f17",
                            border: "1px solid #1a2332",
                            borderRadius: 6,
                          }}>
                            <span style={{ color: step.color, marginTop: 1 }}>◆</span>
                            <span style={{ fontSize: 13, color: "#c9d1d9", lineHeight: 1.5 }}>
                              {c.label}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* Code Preview */}
                      <div>
                        <div style={{
                          display: "flex", justifyContent: "space-between",
                          alignItems: "center", marginBottom: 12,
                        }}>
                          <div style={{
                            fontSize: 10, letterSpacing: 3,
                            color: "#4e5a65", textTransform: "uppercase",
                          }}>
                            程式碼實作
                          </div>
                          <button
                            onClick={(e) => toggleCode(step.id, e)}
                            type="button"
                            style={{
                              background: showCode[step.id]
                                ? step.color + "20"
                                : "transparent",
                              border: `1px solid ${step.color}40`,
                              borderRadius: 4, padding: "3px 10px",
                              fontSize: 11, color: step.color,
                              cursor: "pointer",
                            }}
                          >
                            {showCode[step.id] ? "收起" : "展開"}
                          </button>
                        </div>

                        {showCode[step.id] ? (
                          <pre style={{
                            background: "#060a10",
                            border: "1px solid #1a2332",
                            borderRadius: 6,
                            padding: 14,
                            fontSize: 11,
                            lineHeight: 1.7,
                            color: "#8b949e",
                            overflow: "auto",
                            margin: 0,
                            maxHeight: 280,
                          }}>
                            <code style={{ color: "#e6edf3" }}>{step.code}</code>
                          </pre>
                        ) : (
                          <div style={{
                            background: "#060a10",
                            border: "1px dashed #1a2332",
                            borderRadius: 6,
                            padding: 20,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "#30363d",
                            fontSize: 13,
                            height: 80,
                          }}>
                            點擊「展開」查看 Python 實作
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Connector Arrow */}
              {idx < steps.length - 1 && (
                <div style={{
                  display: "flex", justifyContent: "center",
                  alignItems: "center", height: 36, gap: 6,
                }}>
                  <div style={{
                    width: 1, height: "100%",
                    background: "linear-gradient(#1e2a3a, #1e2a3a)",
                  }} />
                  <div style={{ color: "#2a3f52", fontSize: 18 }}>▼</div>
                </div>
              )}
            </div>
          );
        })}

        {/* Summary Legend */}
        <div style={{
          marginTop: 48,
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 16,
        }}>
          {[
            { label: "✓ PASS", sub: "自動通過，繼續下一關", bg: "#0d2b1a", border: "#22c55e", text: "#4ade80" },
            { label: "⚠ FLAG", sub: "有疑點，標記待複核", bg: "#2b1f0a", border: "#f59e0b", text: "#fbbf24" },
            { label: "✗ ERROR", sub: "明確錯誤，退回重來", bg: "#2b0d0d", border: "#ef4444", text: "#f87171" },
          ].map((item) => (
            <div key={item.label} style={{
              background: item.bg,
              border: `1px solid ${item.border}40`,
              borderRadius: 8,
              padding: "16px 20px",
              textAlign: "center",
            }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: item.text, marginBottom: 4 }}>
                {item.label}
              </div>
              <div style={{ fontSize: 11, color: "#6e7681" }}>{item.sub}</div>
            </div>
          ))}
        </div>

        <div style={{
          marginTop: 24,
          padding: "16px 20px",
          background: "#0a0f17",
          border: "1px solid #1a2332",
          borderRadius: 8,
          fontSize: 12,
          color: "#6e7681",
          textAlign: "center",
          lineHeight: 1.8,
        }}>
          💡 核心思路：把「有經驗的人類審核員會注意什麼」轉成程式規則<br />
          結構 → 數值直覺 → 邏輯一致 → 對照來源 → AI二次審查 → 最終裁決
        </div>
      </div>
    </div>
  );
}
