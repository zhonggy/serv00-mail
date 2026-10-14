"""IMAP 客户端：读邮件列表、读单封、按收件人过滤。"""
import email
import email.header
import email.utils
import imaplib
import re
from email.message import Message


def _decode_header(value) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            out.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _recipient_match(raw: bytes, recipient: str) -> bool:
    """收件人是否精确匹配：解析 To/Cc/Delivered-To/Envelope-To/X-Original-To 中的
    全部邮箱地址，逐个精确比对（不区分大小写）。子字符串匹配会误伤
    （如 test@x 会命中 contest@x），这里必须精确。"""
    target = recipient.strip().lower()
    try:
        msg = email.message_from_bytes(raw)
    except Exception:
        return False
    headers = []
    for name in ("To", "Cc", "Delivered-To", "Envelope-To", "X-Original-To"):
        v = msg.get(name)
        if v:
            headers.append(_decode_header(v))
    for _, addr in email.utils.getaddresses(headers):
        if addr.strip().lower() == target:
            return True
    return False


def _get_body(msg: Message) -> tuple[str, str | None]:
    """返回 (纯文本, html或None)。"""
    text, html = "", None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = part.get("Content-Disposition", "")
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if ctype == "text/plain" and not text:
                text = content
            elif ctype == "text/html" and html is None:
                html = content
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html = content
            else:
                text = content
    return text.strip(), html


class ImapClient:
    """with 语句使用的 IMAP 连接。"""

    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.conn: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> "ImapClient":
        self.conn = imaplib.IMAP4_SSL(self.host, self.port)
        self.conn.login(self.username, self.password)
        return self

    def __exit__(self, *exc):
        try:
            if self.conn:
                self.conn.logout()
        except Exception:
            pass
        self.conn = None

    def _parse(self, uid: str, raw: bytes) -> dict:
        msg = email.message_from_bytes(raw)
        body_text, body_html = _get_body(msg)
        return {
            "uid": uid,
            "subject": _decode_header(msg.get("Subject")),
            "from": _decode_header(msg.get("From")),
            "to": _decode_header(msg.get("To")),
            "date": msg.get("Date", ""),
            "snippet": body_text[:200].replace("\n", " "),
            "body_text": body_text,
            "body_html": body_html,
        }

    def _uid_search(self, folder: str = "INBOX") -> list[str]:
        """返回 UID 列表（从旧到新）。用 UID 而不用 sequence number，
        因为删信后 sequence number 会移位，UID 不变。"""
        assert self.conn
        self.conn.select(folder, readonly=True)
        typ, data = self.conn.uid("search", None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return []
        return [u.decode() for u in data[0].split()]

    def list_uids(self, folder: str = "INBOX") -> list[str]:
        """只取 UID 列表（从旧到新），用于增量同步。"""
        return self._uid_search(folder)

    def set_seen(self, uids: list[str], seen: bool = True,
                 folder: str = "INBOX") -> None:
        """标记已读/未读（Seen flag）。"""
        if not uids:
            return
        assert self.conn
        self.conn.select(folder)
        op = "+FLAGS" if seen else "-FLAGS"
        for uid in uids:
            self.conn.uid("STORE", uid, op, "(\\Seen)")

    def delete_uids(self, uids: list[str], folder: str = "INBOX") -> None:
        """彻底删除邮件（+\\Deleted + expunge）。"""
        if not uids:
            return
        assert self.conn
        self.conn.select(folder)
        for uid in uids:
            self.conn.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
        self.conn.expunge()

    def match_uids_by_recipient(self, uids: list[str], recipient: str,
                                folder: str = "INBOX") -> list[str]:
        """只取邮件头，按收件人过滤 UID（别名共享主邮箱时用，避免拉正文）。"""
        if not uids or not recipient:
            return list(uids)
        assert self.conn
        self.conn.select(folder, readonly=True)
        matched = []
        target = recipient.lower()
        for i in range(0, len(uids), 50):
            batch = ",".join(uids[i:i + 50])
            typ, data = self.conn.uid("fetch", batch, "(BODY.PEEK[HEADER])")
            if typ != "OK" or not data:
                continue
            for item in data:
                if not isinstance(item, tuple) or len(item) < 2 or not item[1]:
                    continue
                head = item[0].decode(errors="replace")
                m = re.search(r"UID (\d+)", head)
                if not m:
                    continue
                uid = m.group(1)
                msg = email.message_from_bytes(item[1])
                to = _decode_header(msg.get("To"))
                if target in to.lower():
                    matched.append(uid)
                    continue
                delivered = (_decode_header(msg.get("Delivered-To"))
                             + _decode_header(msg.get("Envelope-To"))
                             + _decode_header(msg.get("X-Original-To")))
                if target in delivered.lower():
                    matched.append(uid)
        return matched

    def get_flags(self, uids: list[str], folder: str = "INBOX") -> dict[str, bool]:
        """返回 {uid: 是否已读}。"""
        out: dict[str, bool] = {}
        if not uids:
            return out
        assert self.conn
        self.conn.select(folder, readonly=True)
        # 分批，避免命令行过长
        for i in range(0, len(uids), 100):
            batch = ",".join(uids[i:i + 100])
            typ, data = self.conn.uid("fetch", batch, "(FLAGS)")
            if typ != "OK" or not data:
                continue
            for item in data:
                if not isinstance(item, tuple) or len(item) < 2:
                    continue
                # UID FETCH 返回头形如 b'7 (UID 123 FLAGS (\\Seen))'，UID 在括号内
                head = item[0].decode(errors="replace")
                m = re.search(r"UID (\d+)", head)
                if m:
                    out[m.group(1)] = "\\Seen" in head
        return out

    def list_messages(self, folder: str = "INBOX", limit: int = 20,
                      recipient: str | None = None) -> list[dict]:
        """列出邮件。recipient 非空时只返回收件人匹配的（给别名方案用）。"""
        assert self.conn
        self.conn.select(folder, readonly=True)
        uids = self._uid_search_raw()
        result = []
        for uid in reversed(uids[-limit * 3:]):  # 多取一点再过滤
            typ, fetched = self.conn.uid("fetch", uid, "(RFC822)")
            if typ != "OK" or not fetched or not fetched[0]:
                continue
            if recipient and not _recipient_match(fetched[0][1], recipient):
                continue
            parsed = self._parse(uid, fetched[0][1])
            result.append(parsed)
            if len(result) >= limit:
                break
        return result

    def _uid_search_raw(self) -> list[str]:
        """select 之后直接取 UID（内部用，避免重复 select）。"""
        assert self.conn
        typ, data = self.conn.uid("search", None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return []
        return [u.decode() for u in data[0].split()]

    def fetch_message(self, uid: str, folder: str = "INBOX",
                      recipient: str | None = None) -> dict | None:
        assert self.conn
        self.conn.select(folder, readonly=True)
        typ, fetched = self.conn.uid("fetch", uid, "(RFC822)")
        if typ != "OK" or not fetched or not fetched[0]:
            return None
        parsed = self._parse(uid, fetched[0][1])
        if recipient and not _recipient_match(fetched[0][1], recipient):
            return None
        return parsed

    def latest_messages(self, limit: int = 10, recipient: str | None = None,
                        since_minutes: int = 10) -> list[dict]:
        """取最近的邮件（验证码场景用，按需拉取即可）。"""
        # 简单起见：直接取最新 limit*2 封再按时间过滤，由上层处理
        return self.list_messages(limit=limit * 2, recipient=recipient)[:limit]
