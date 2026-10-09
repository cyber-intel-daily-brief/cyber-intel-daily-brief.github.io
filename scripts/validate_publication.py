import json, re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

class ReportMeta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "report-id":
            self.ids.append(attrs.get("content"))

def require(condition, message):
    if not condition:
        raise ValueError(message)

def validate(root):
    root = Path(root)
    payload = json.loads((root / "line-payload.json").read_text(encoding="utf-8"))
    report_id = payload.get("report_id", "")
    match = re.fullmatch(r"CIB-(\d{8})-(\d{4})", report_id)
    require(match is not None, "Invalid report_id")
    day = datetime.strptime(match[1], "%Y%m%d").strftime("%Y-%m-%d")
    datetime.strptime(match[2], "%H%M")
    expected_url = "https://cyber-intel-daily-brief.github.io/archive/" + day + "/"
    for name in ("index.html", "archive/" + day + "/index.html"):
        parser = ReportMeta()
        parser.feed((root / name).read_text(encoding="utf-8"))
        require(parser.ids == [report_id], "Report ID mismatch: " + name)
    archive = (root / "archive/index.html").read_text(encoding="utf-8")
    require(report_id in archive and day + "/" in archive, "Archive listing missing current report")
    messages = payload.get("broadcast", {}).get("messages")
    require(isinstance(messages, list) and 1 <= len(messages) <= 5, "Invalid messages array")
    require(any(m.get("type") == "text" for m in messages), "Text summary missing")
    require(any(m.get("type") == "flex" for m in messages), "Flex message missing")
    buttons = []
    def walk(value):
        if isinstance(value, dict):
            action = value.get("action", {})
            if isinstance(action, dict) and action.get("label") == "ดูรายละเอียดเต็ม":
                buttons.append(action)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for message in messages:
        require(isinstance(message, dict), "Message must be an object")
        if message.get("type") == "text":
            value = message.get("text", "")
            require(isinstance(value, str) and 0 < len(value) <= 5000, "Invalid text summary")
            require("cyber-intel-daily-brief.github.io" not in value, "Raw dashboard URL in summary")
        elif message.get("type") == "flex":
            alt = message.get("altText", "")
            require(isinstance(alt, str) and 0 < len(alt) <= 400, "Invalid Flex altText")
            walk(message.get("contents"))
        else:
            raise ValueError("Unsupported Daily Brief message type")
    require(buttons and all(a.get("type") == "uri" and a.get("uri") == expected_url for a in buttons),
            "Detail button must point to today's archive")
    return report_id, day

if __name__ == "__main__":
    import os
    report_id, day = validate(".")
    print("Publication preflight PASS: " + report_id)
    env = os.environ.get("GITHUB_ENV")
    if env:
        with open(env, "a", encoding="utf-8") as output:
            output.write("REPORT_ID=" + report_id + "\nREPORT_DATE=" + day + "\n")
