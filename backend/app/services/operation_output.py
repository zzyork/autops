import codecs
import re
import threading

MAX_TEXT = 8192
TRUNCATED = "[较早输出已截断]"
HIDDEN_URL = "[URL 已隐藏]"
HIDDEN_VALUE = "[敏感信息已隐藏]"
URL = re.compile(r"(?i)https?://")
LABEL = re.compile(r"(?i)(?:password|passwd|token|secret|credential|gpgkey|api[_-]?key|authorization)\s*[:=]\s*")
LABEL_START = re.compile(r"(?i)(?:password|passwd|token|secret|credential|gpgkey|api[_-]?key|authorization)\s*$")
PREFIXES = ("http://", "https://", "password", "passwd", "token", "secret", "credential", "gpgkey",
            "api_key", "api-key", "authorization")
URL_END = set(" \t\r\n\"'<>`")


class _Stream:
    def __init__(self) -> None:
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.lines = ""
        self.line = ""
        self.pending = ""
        self.hidden: str | None = None
        self.escape: str | None = None
        self.truncated = False
        self.cr = False
        self.finished = False

    def _bound(self) -> None:
        limit = MAX_TEXT - len(TRUNCATED)
        if len(self.lines) + len(self.line) > MAX_TEXT:
            self.truncated = True
        if self.truncated:
            excess = len(self.lines) + len(self.line) - limit
            if excess > 0:
                removed = min(excess, len(self.lines))
                self.lines = self.lines[removed:]
                self.line = self.line[excess - removed:]

    def _write(self, text: str) -> None:
        self.line += text
        self._bound()

    def _safe(self, final: bool = False) -> None:
        while self.pending:
            url = URL.search(self.pending)
            label = LABEL.search(self.pending)
            matches = [(match.start(), match.end(), kind) for kind, match in (("url", url), ("label", label)) if match]
            if matches:
                start, end, kind = min(matches)
                self._write(self.pending[:start])
                self.pending = self.pending[end:]
                self._write(HIDDEN_URL if kind == "url" else HIDDEN_VALUE)
                self.hidden = kind
                return
            keep = 0
            if not final:
                keep = max((size for size in range(1, min(len(self.pending), 64) + 1)
                            if any(word.startswith(self.pending[-size:].lower()) for word in PREFIXES)), default=0)
                start = LABEL_START.search(self.pending)
                if start:
                    keep = max(keep, len(self.pending) - start.start())
                if keep > 64:
                    self._write(self.pending[:start.start()])
                    self.pending = ""
                    self._write(HIDDEN_VALUE)
                    self.hidden = "label"
                    return
            length = max(0, len(self.pending) - keep)
            if not length:
                return
            self._write(self.pending[:length])
            self.pending = self.pending[length:]

    def _character(self, char: str) -> None:
        if self.escape:
            if self.escape == "esc":
                self.escape = ("csi" if char == "[" else "osc" if char == "]" else
                               "string" if char in "PX^_" else None)
            elif self.escape == "csi":
                if "@" <= char <= "~":
                    self.escape = None
            elif self.escape in ("osc", "string"):
                if char == "\x07":
                    self.escape = None
                elif char == "\x1b":
                    self.escape += "_esc"
            elif self.escape in ("osc_esc", "string_esc"):
                self.escape = None if char == "\\" else self.escape.removesuffix("_esc")
            return
        if char == "\x1b":
            self.escape = "esc"
            return
        if char in ("\x9b", "\x9d", "\x90", "\x98", "\x9e", "\x9f"):
            self.escape = "csi" if char == "\x9b" else "osc" if char == "\x9d" else "string"
            return
        if self.cr:
            self.cr = False
            if char == "\n":
                self.lines += self.line + "\n"
                self.line = ""
                self._bound()
                return
            self.line = ""
        if self.hidden:
            delimiter = char in URL_END if self.hidden == "url" else char in "\r\n"
            if not delimiter:
                return
            self.hidden = None
        if char == "\r" or char == "\n":
            self._safe(final=True)
            if char == "\r":
                self.cr = True
            else:
                self.lines += self.line + "\n"
                self.line = ""
            self._bound()
        elif char == "\t" or char >= " " and char != "\x7f" and not "\x80" <= char <= "\x9f":
            self.pending += char
            self._safe()

    def feed(self, data: bytes) -> None:
        for char in self.decoder.decode(data):
            self._character(char)

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        for char in self.decoder.decode(b"", final=True):
            self._character(char)
        self._safe(final=True)
        self.hidden = None
        self.escape = None
        self.cr = False

    def snapshot(self) -> str:
        text = self.lines + self.line
        return TRUNCATED + text if self.truncated else text


class OperationOutput:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.streams = {"stdout": _Stream(), "stderr": _Stream()}
        self.version = 0

    def feed(self, stream: str, data: bytes) -> None:
        with self.lock:
            if self.streams[stream].finished:
                raise ValueError("已结束的输出流不能继续写入")
            self.streams[stream].feed(data)
            if data:
                self.version += 1

    def finish(self) -> None:
        with self.lock:
            if all(stream.finished for stream in self.streams.values()):
                return
            for stream in self.streams.values():
                stream.finish()
            self.version += 1

    def snapshot(self) -> tuple[int, str, str]:
        with self.lock:
            return self.version, self.streams["stdout"].snapshot(), self.streams["stderr"].snapshot()


def safe_saved_text(value: str | None) -> str | None:
    if value is None:
        return None
    if (len(value) <= MAX_TEXT and not URL.search(value) and not LABEL.search(value)
            and not any((ord(char) < 32 and char not in "\n\t") or 127 <= ord(char) < 160
                        for char in value)):
        return value
    output = OperationOutput()
    output.feed("stdout", value.encode("utf-8"))
    output.finish()
    return output.snapshot()[1]
