import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            padding: "32px 24px",
            margin: "16px",
            borderRadius: 12,
            border: "1px solid rgba(248,113,113,0.3)",
            background: "rgba(248,113,113,0.08)",
            color: "#fecaca",
            fontSize: 13,
            lineHeight: 1.6,
          }}
          role="alert"
        >
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 8 }}>⚠ 頁面渲染錯誤</div>
          <div style={{ color: "var(--muted)", marginBottom: 12 }}>
            {this.state.error?.message ?? "未知錯誤"}
          </div>
          <button
            type="button"
            onClick={() => {
              this.setState({ error: null });
              window.location.reload();
            }}
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              border: "1px solid rgba(248,113,113,0.4)",
              background: "transparent",
              color: "#fecaca",
              fontSize: 12,
              cursor: "pointer",
            }}
            aria-label="重新載入頁面"
          >
            重新載入
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
