"""Telegram message sending, HTML sanitization, and gate alert utilities.

Extracted from main.py to reduce module size. All Telegram-specific
logic lives here; the pipeline orchestrator imports what it needs.
"""

import html
import logging
import os
import re
import time
from datetime import datetime, timezone

import telebot

logger = logging.getLogger(__name__)

# Telegram HTML 支援的標籤白名單（與專案規範一致，不含 <pre>）
_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "blockquote", "a"}


def sanitize_telegram_html(text: str) -> str:
    """清洗 LLM 輸出的 HTML，保留 Telegram 支援標籤並修復失衡標籤。"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n")
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', text)

    placeholders: dict[str, str] = {}
    seq = 0

    def _stash(val: str) -> str:
        nonlocal seq
        key = f"__TG_TAG_{seq}__"
        placeholders[key] = val
        seq += 1
        return key

    def _keep_anchor_open(m: re.Match) -> str:
        href_m = re.search(r'href=["\']([^"\']+)["\']', m.group(0), re.IGNORECASE)
        if not href_m:
            return ""
        href = html.escape(html.unescape(href_m.group(1)), quote=True)
        return _stash(f'<a href="{href}">')

    text = re.sub(r'<a\b[^>]*>', _keep_anchor_open, text, flags=re.IGNORECASE)
    text = re.sub(r'</a\s*>', lambda _m: _stash("</a>"), text, flags=re.IGNORECASE)
    text = re.sub(
        r'</?(?:b|i|u|s|code|blockquote)\s*>',
        lambda m: _stash(m.group(0).lower()),
        text,
        flags=re.IGNORECASE,
    )

    # 先把所有殘餘尖括號轉義，避免 `<0.03)</code>` 這類非標籤片段炸掉 Telegram parser。
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    for key, val in placeholders.items():
        text = text.replace(key, val)

    return _balance_telegram_html_tags(text)


def _balance_telegram_html_tags(text: str) -> str:
    """移除不合法 closing tag，並為未關閉 tag 自動補齊結尾。"""
    tag_re = re.compile(
        r'</?(?:b|i|u|s|code|blockquote|a)(?:\s+href="[^"]*")?\s*>',
        re.IGNORECASE,
    )
    out: list[str] = []
    stack: list[str] = []
    last = 0
    for m in tag_re.finditer(text):
        out.append(text[last:m.start()])
        tag = m.group(0)
        name_m = re.match(r'</?\s*([a-z]+)', tag, re.IGNORECASE)
        if not name_m:
            last = m.end()
            continue
        name = name_m.group(1).lower()
        is_close = tag.startswith("</")

        if not is_close:
            if name == "a":
                if not re.match(r'<a\s+href="[^"]*">', tag, re.IGNORECASE):
                    last = m.end()
                    continue
                out.append(tag)
            else:
                out.append(f"<{name}>")
            stack.append(name)
        else:
            if stack and stack[-1] == name:
                out.append(f"</{name}>")
                stack.pop()
            # unmatched closing tag -> drop
        last = m.end()

    out.append(text[last:])
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)


def strip_html(text: str) -> str:
    """完全移除所有 HTML 標籤，回傳純文字。"""
    return re.sub(r'<[^>]+>', '', text)


def _safe_chunks(text: str, max_len: int = 4000) -> list[str]:
    """切分訊息，優先在區段分隔線處切割，避免切斷新聞/推文條目。"""
    if not text:
        return [""]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        cut = remaining.rfind("────────────", 0, max_len + 1)
        if cut > max_len // 2:
            cut += len("────────────")
        else:
            section_matches = list(re.finditer(r'\n【', remaining[:max_len + 1]))
            if section_matches:
                cut = section_matches[-1].start()
            else:
                cut = remaining.rfind("\n", 0, max_len + 1)
                if cut == -1:
                    cut = max_len

        candidate = remaining[:cut]
        if candidate.count("<") > candidate.count(">"):
            last_open = candidate.rfind("<")
            if last_open > 0:
                cut = last_open

        if cut <= 0:
            cut = max_len
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")

    if remaining:
        chunks.append(remaining)
    return chunks


def _send_telegram_report(text: str, token: str, chat_id: str, image_path: str = "daily_chart.png") -> None:
    """發送戰報至 Telegram：若有圖表則先發圖，再分段發送文字；含重試與 fallback。"""
    from telebot import apihelper

    apihelper.SESSION_TIME_TO_LIVE = 5 * 60
    bot = telebot.TeleBot(token)

    if os.path.exists(image_path):
        for attempt in range(3):
            try:
                with open(image_path, "rb") as f:
                    bot.send_photo(chat_id, photo=f, timeout=60)
                break
            except Exception as e:
                logger.warning("send_photo attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))

    html_mode = True
    for i, raw_chunk in enumerate(_safe_chunks(text)):
        chunk = sanitize_telegram_html(raw_chunk)
        plain_chunk = strip_html(chunk)
        sent = False
        for attempt in range(4):
            try:
                if html_mode:
                    bot.send_message(chat_id, chunk, parse_mode="HTML", timeout=60)
                else:
                    bot.send_message(chat_id, plain_chunk, timeout=60)
                sent = True
                time.sleep(0.5)
                break
            except Exception as e:
                err_str = str(e).lower()
                if html_mode and "can't parse entities" in err_str:
                    logger.warning("Chunk %d HTML parse failed; downgrade to plain text mode: %s", i, e)
                    html_mode = False
                    continue
                wait = 5 if "429" not in err_str else 30 * (attempt + 1)
                logger.warning("Chunk %d send attempt %d failed (wait=%ds): %s", i, attempt + 1, wait, e)
                if attempt < 3:
                    time.sleep(wait)
        if not sent:
            try:
                bot.send_message(chat_id, plain_chunk, timeout=60)
            except Exception as final_e:
                logger.error("Chunk %d all retries failed: %s", i, final_e)


# Gate 告警錯誤碼（供 Telegram 關鍵字過濾）
GATE_CODE_CRITICAL_SOURCE = "GATE_CRITICAL_SOURCE"
GATE_CODE_LLM_DISCONNECT = "GATE_LLM_DISCONNECT"
GATE_CODE_EXECUTION_FAILED = "GATE_EXECUTION_FAILED"
GATE_CODE_VALIDATION = "GATE_VALIDATION"
GATE_CODE_UNKNOWN = "GATE_UNKNOWN"


def _format_gate_issues_followup_messages(all_issues: list[str]) -> list[str]:
    """純文字 follow-up（不用 HTML parse_mode），避免長 issue 炸 Telegram entity。"""
    if not all_issues:
        return []
    header = (
        f"📋 Q-Silicon 驗證問題清單（共 {len(all_issues)} 項）\n"
        "下列為 validate_report 完整 issues；正式戰報未推送。\n"
        "────────────────────────"
    )
    chunks: list[str] = []
    cur = header
    max_body = 3600
    for idx, issue in enumerate(all_issues, start=1):
        line = f"\n{idx}. {issue}"
        if len(cur) + len(line) > max_body:
            chunks.append(cur)
            cur = f"（續）\n{idx}. {issue}"
        else:
            cur += line
    if cur.strip():
        chunks.append(cur)
    return chunks


def _gate_alert_severity_and_code(
    top_issues: str | None,
    error_text: str | None,
    *,
    all_issues_list: list[str] | None = None,
) -> tuple[str, str]:
    """依 top_issues 與 error_text 決定 severity 與固定錯誤碼。"""
    issues = (top_issues or "").strip().lower()
    err = (error_text or "").strip().lower()
    issues_blob = (top_issues or "") + "\n" + "\n".join(all_issues_list or [])

    if "關鍵資料來源缺失" in issues_blob:
        return "CRITICAL", GATE_CODE_CRITICAL_SOURCE
    if err and err != "n/a":
        if "server disconnected" in err or "disconnected without sending" in err:
            return "WARNING", GATE_CODE_LLM_DISCONNECT
        if "503" in err or "unavailable" in err or "rate limit" in err:
            return "WARNING", GATE_CODE_LLM_DISCONNECT
        return "CRITICAL", GATE_CODE_EXECUTION_FAILED
    if (issues and issues != "n/a") or (all_issues_list and len(all_issues_list) > 0):
        return "WARNING", GATE_CODE_VALIDATION
    return "WARNING", GATE_CODE_UNKNOWN


def _send_telegram_gate_alert(
    token: str,
    chat_id: str,
    top_issues: str | None = None,
    error_text: str | None = None,
    *,
    all_issues: list[str] | None = None,
    artifact_rel: str | None = None,
    last_success_time_utc: str | None = None,
) -> None:
    """一致性 gate 阻擋時，發送簡短告警到 Telegram（含 severity 與固定錯誤碼）。"""
    if not token or not chat_id:
        return

    bot = telebot.TeleBot(token)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    issue_line = top_issues.strip() if (top_issues or "").strip() else "N/A"
    err_line = (error_text or "").strip()
    if len(err_line) > 240:
        err_line = err_line[:240] + "..."
    if not err_line:
        err_line = "N/A"
    last_ok = last_success_time_utc
    n_issues = len(all_issues) if all_issues else 0
    severity, code = _gate_alert_severity_and_code(
        top_issues, error_text, all_issues_list=all_issues
    )
    art_line = (artifact_rel or "").strip() or "N/A"

    alert_text = (
        "<b>Q-Silicon Gate 告警</b>\n"
        f"<code>code: {code}</code>\n"
        f"<code>severity: {severity}</code>\n"
        f"<code>STRICT_CONSISTENCY_GATE=1</code> 已阻擋本次正式戰報推送。\n"
        f"<code>time: {ts}</code>\n"
        f"<code>last_success: {last_ok or 'N/A'}</code>\n"
        f"<code>issues_count: {n_issues}</code>\n"
        f"<code>artifacts: {art_line}</code>\n"
        f"<code>top_issues: {issue_line}</code>\n"
        f"<code>error: {err_line}</code>"
    )
    safe_alert = sanitize_telegram_html(alert_text)
    try:
        bot.send_message(chat_id, safe_alert, parse_mode="HTML", timeout=30)
        logger.info("Gate alert sent to Telegram.")
    except Exception as e:
        logger.warning("Failed to send gate alert to Telegram: %s", e)

    if (
        _gate_alert_send_full_issues()
        and all_issues
        and len(all_issues) > 0
        and code == GATE_CODE_VALIDATION
    ):
        for chunk in _format_gate_issues_followup_messages(all_issues):
            try:
                bot.send_message(chat_id, chunk, timeout=60)
            except Exception as e:
                logger.warning("Failed to send gate issues follow-up: %s", e)
                break


def _gate_alert_send_full_issues() -> bool:
    return os.getenv("GATE_ALERT_FULL_ISSUES", "1").lower() not in ("0", "false", "no")
