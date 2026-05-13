export default function NewsHome() {
  return (
    <div data-testid="news-home" className="px-3 py-4 pb-24">
      <div className="page-header">
        <div className="page-title">科技即時報</div>
        <div className="page-subtitle">Tech pulse digest 接線預留（隊列 40）；本切片只建立路由框架。</div>
      </div>

      <div className="card" role="status">
        <div className="card-title">尚未接入即時新聞來源</div>
        <p className="m-0 text-[13px] leading-snug text-[var(--muted)]">
          Firestore digest、主題 filter 與 deep brief side panel 將在後續隊列實作；目前不顯示未溯源新聞。
        </p>
      </div>
    </div>
  );
}
