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
            border: "1px solid rgba(220,38,38,0.2)",
            background: "rgba(220,38,38,0.06)",
            color: "var(--red, #dc2626)",
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
              border: "1px solid rgba(220,38,38,0.3)",
              background: "transparent",
              color: "var(--red, #dc2626)",
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
