/** 顯示 API／BQ 之 ISO 時間戳（zh-TW） */
export function formatAsOfZh(v) {
  if (v == null || v === "") return "N/A";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString("zh-TW");
}
