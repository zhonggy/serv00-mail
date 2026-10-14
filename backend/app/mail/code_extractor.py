"""从邮件正文/主题中提取验证码。纯正则方案，覆盖绝大多数场景。"""
import html as _html
import re
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    """把 HTML 转纯文本：去标签、解实体、script/style 内容丢弃。"""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        raw = _html.unescape("".join(self._parts))
        # 压缩空白：多个空行/空格合并
        raw = re.sub(r"[ \t\u00a0]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n", raw)
        return raw.strip()


def html_to_text(html_str: str) -> str:
    if not html_str:
        return ""
    p = _TextExtractor()
    try:
        p.feed(html_str)
    except Exception:
        pass
    return p.text()

# (正则, 备注)。按优先级排序。简繁中文关键词都覆盖。
PATTERNS: list[tuple[str, str]] = [
    # 中文：验证码是 123456 / 確認碼 016939
    (r"(?:验证码|驗證碼|校验码|动态码|安全码|确认码|確認碼)[^\d]{0,12}(\d{4,8})", "zh"),
    # 英文：verification code is 123456 / OTP: 123456
    (r"(?:verification code|verify code|otp|one-?time password|security code)[^\d]{0,12}(\d{4,8})", "en"),
    # 通用兜底：连续 4-8 位数字（前后不是更长数字串）
    (r"(?<!\d)(\d{4,8})(?!\d)", "generic"),
]


def extract_codes(text: str, max_codes: int = 3) -> list[dict]:
    """返回 [{"code": ..., "context": ...}]，按 pattern 优先级去重。"""
    if not text:
        return []
    found: list[dict] = []
    seen: set[str] = set()
    for pattern, lang in PATTERNS:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            code = m.group(1)
            if code in seen:
                continue
            # 兜底 pattern 容易误伤年份/金额，只保留它前面 20 字内有"码"字语境的（简繁都认）
            if lang == "generic":
                window = text[max(0, m.start() - 20):m.start()]
                if not re.search(r"码|碼|code|otp|验证|驗證|校验", window, flags=re.IGNORECASE):
                    continue
            seen.add(code)
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            context = text[start:end].replace("\n", " ").strip()
            found.append({"code": code, "context": context})
            if len(found) >= max_codes:
                return found
    return found


def extract_from_message(parsed: dict, max_codes: int = 3) -> list[dict]:
    """对一封已解析的邮件提取验证码，附带发件人/主题/时间。
    纯 HTML 邮件没有 text/plain 时，回退到对 body_html 去标签后提取。"""
    body_text = parsed.get("body_text", "") or ""
    if not body_text.strip():
        body_text = html_to_text(parsed.get("body_html", "") or "")
    haystack = f"{parsed.get('subject', '')}\n{body_text}"
    codes = extract_codes(haystack, max_codes=max_codes)
    for c in codes:
        c["from"] = parsed.get("from", "")
        c["subject"] = parsed.get("subject", "")
        c["date"] = parsed.get("date", "")
    return codes
