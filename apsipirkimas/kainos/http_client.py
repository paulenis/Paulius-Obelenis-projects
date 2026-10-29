"""Small polite HTTP client on the standard library (no extra installs needed)."""

import json
import time
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)


class FetchError(Exception):
    pass


class Client:
    def __init__(self, delay=0.7, timeout=30, retries=2):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self._last = 0.0

    def _wait(self):
        pause = self.delay - (time.monotonic() - self._last)
        if pause > 0:
            time.sleep(pause)
        self._last = time.monotonic()

    def request(self, url, data=None, headers=None):
        hdrs = {"User-Agent": USER_AGENT, "Accept-Language": "lt-LT,lt;q=0.9"}
        hdrs.update(headers or {})
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        last_error = None
        for attempt in range(self.retries + 1):
            self._wait()
            try:
                req = urllib.request.Request(url, data=body, headers=hdrs)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code} – {url}"
                if e.code in (403, 404):
                    break  # blocked or gone: retrying will not help
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_error = f"{e} – {url}"
            time.sleep(2 * (attempt + 1))
        raise FetchError(last_error)

    def get(self, url, headers=None):
        return self.request(url, headers=headers)

    def post_json(self, url, payload, headers=None):
        return self.request(url, data=payload, headers=headers)
