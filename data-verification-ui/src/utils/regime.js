export function regimeInfo(score) {
  if (score == null) return { label: "— 未知", cls: "regime-neutral", text: "未知", color: "var(--muted)" };
  if (score >= 3.5) return { label: "🔴 Risk OFF", cls: "regime-off",     text: "Risk OFF", color: "var(--red)" };
  if (score >= 2.5) return { label: "🟡 中性",     cls: "regime-neutral", text: "中性",     color: "var(--yellow)" };
  return               { label: "🟢 Risk ON",  cls: "regime-on",      text: "Risk ON",  color: "var(--green)" };
}
