"""钉钉自定义机器人推送（支持加签安全设置）。

仅依赖标准库，可在云端无头环境直接运行。
文档：https://open.dingtalk.com/document/robots/custom-robot-access
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request


def _sign(secret: str):
    """返回 (timestamp, sign) 用于加签。"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode("utf-8"),
                         string_to_sign.encode("utf-8"),
                         digestmod=hashlib.sha256).digest()
    return timestamp, base64.b64encode(hmac_code).decode("utf-8")


def push_markdown(webhook: str, secret: str, title: str, text: str) -> str:
    """推送 markdown 消息。成功返回钉钉响应文本，失败返回 ERROR:...。"""
    url = webhook
    if secret:
        ts, sign = _sign(secret)
        url = f"{webhook}&timestamp={ts}&sign={urllib.parse.quote_plus(sign)}"

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


if __name__ == "__main__":
    ts, sg = _sign("test-secret")
    print("timestamp=", ts, "sign=", sg)
