/**
 * 依 BigQuery OPEN 持倉筆數顯示曝險紅綠燈（機構風控一覽）。
 * 0–2 綠、3–4 黃、≥5 紅。
 */
export default function PositionHealthStrip({ openCount, loading, error }) {
  if (error) {
    return (
      <div
        className="glassbox-health glassbox-health--error"
        role="status"
        aria-live="polite"
      >
        <span className="glassbox-health__lights" aria-hidden>
          <span className="glassbox-health__dot glassbox-health__dot--off" />
          <span className="glassbox-health__dot glassbox-health__dot--off" />
          <span className="glassbox-health__dot glassbox-health__dot--warn" />
        </span>
        <div className="glassbox-health__text">
          <strong>部位信號</strong>
          <span className="glassbox-health__sub">無法載入 OPEN 持倉（{error.message || "錯誤"}）</span>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="glassbox-health glassbox-health--loading" role="status" aria-busy="true">
        <span className="glassbox-health__lights" aria-hidden>
          <span className="glassbox-health__dot glassbox-health__dot--pulse" />
          <span className="glassbox-health__dot glassbox-health__dot--pulse" />
          <span className="glassbox-health__dot glassbox-health__dot--pulse" />
        </span>
        <div className="glassbox-health__text">
          <strong>部位信號</strong>
          <span className="glassbox-health__sub">同步持倉中…</span>
        </div>
      </div>
    );
  }

  const n = typeof openCount === "number" ? openCount : 0;
  let level = "ok";
  let label = "曝險正常";
  if (n >= 5) {
    level = "high";
    label = "曝險偏高";
  } else if (n >= 3) {
    level = "warn";
    label = "曝險留意";
  }

  return (
    <div
      className={`glassbox-health glassbox-health--${level}`}
      role="status"
      aria-label={`運行中部位 ${n} 筆，${label}`}
    >
      <span className="glassbox-health__lights" aria-hidden>
        <span
          className={`glassbox-health__dot ${
            level === "ok" ? "glassbox-health__dot--on-green" : "glassbox-health__dot--off"
          }`}
        />
        <span
          className={`glassbox-health__dot ${
            level === "warn" ? "glassbox-health__dot--on-yellow" : "glassbox-health__dot--off"
          }`}
        />
        <span
          className={`glassbox-health__dot ${
            level === "high" ? "glassbox-health__dot--on-red" : "glassbox-health__dot--off"
          }`}
        />
      </span>
      <div className="glassbox-health__text">
        <strong>部位健康度</strong>
        <span className="glassbox-health__sub">
          OPEN <code>{n}</code> 筆 · {label}
          {level === "high" && " — 建議檢視總曝險與相關性"}
        </span>
      </div>
    </div>
  );
}
