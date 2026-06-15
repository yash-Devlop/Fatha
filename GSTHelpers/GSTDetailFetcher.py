import http.client
import json
import re
import socket
import time

from PySide6.QtCore import QThread, Signal

# SECRET FILE HEADERS ( API HEADER FOR FETCHING GST DETAILS USING RAPIDAPI )
# headers = {
#     'x-rapidapi-key': {rapid api key},
#     'x-rapidapi-host': {rapid api host},
#     'Content-Type': "application/json"
# }

try:
    from GSTHelpers.secret import headers as _API_HEADERS
except ImportError:
    _API_HEADERS = {}

GST_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[0-9A-Z]$"

def check_internet(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
        return True
    except OSError:
        return False


def get_details(gst_no: str, retries: int = 3, timeout: int = 5) -> dict | None:
    gst_no = gst_no.strip().upper()

    if not re.match(GST_REGEX, gst_no):
        print(f"[GSTDetailFetcher] Invalid GST format: {gst_no!r}")
        return None

    if not _API_HEADERS:
        print("[GSTDetailFetcher] No API headers found — check secret.py")
        return None

    for attempt in range(1, retries + 1):
        conn = None
        try:
            conn = http.client.HTTPSConnection(
                "gst-insights-api.p.rapidapi.com",
                timeout=timeout,
            )
            conn.request("GET", f"/getGSTDetailsUsingGST/{gst_no}", headers=_API_HEADERS)
            res = conn.getresponse()

            if res.status != 200:
                print(f"[GSTDetailFetcher] HTTP {res.status} {res.reason}")
                return None

            raw = res.read()
            if not raw:
                print("[GSTDetailFetcher] Empty response body")
                return None

            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                print("[GSTDetailFetcher] Response is not valid JSON")
                return None

        except socket.timeout:
            print(f"[GSTDetailFetcher] Timeout on attempt {attempt}/{retries}")

        except http.client.HTTPException as exc:
            print(f"[GSTDetailFetcher] HTTP error: {exc}")
            return None

        except OSError as exc:
            print(f"[GSTDetailFetcher] Network error: {exc}")
            return None

        except Exception as exc:
            print(f"[GSTDetailFetcher] Unexpected error: {exc}")
            return None

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        if attempt < retries:
            print(f"[GSTDetailFetcher] Retrying ({attempt}/{retries}) …")
            time.sleep(2)

    print("[GSTDetailFetcher] All retries exhausted")
    return None

class GSTFetchWorker(QThread):
    result_ready = Signal(dict)
    error        = Signal(str)
    def __init__(self, gst_no: str):
        super().__init__()
        self._gst_no = gst_no

    def run(self):
        from GSTHelpers.GSTDetailFetcher import get_details, check_internet
        if not check_internet():
            self.error.emit("no_internet")
            return
        data = get_details(self._gst_no)
        if data:
            self.result_ready.emit(data)
        else:
            self.error.emit("api_error")
