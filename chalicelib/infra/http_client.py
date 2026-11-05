import urllib.error
import urllib.request

from chalicelib.shared.http import HttpRequest, HttpResponse

MAX_BODY_BYTES = 256 * 1024
USER_AGENT = 'chalice-api-monitor/1.0'


class UrllibHttpClient:
    """Cliente HTTP só com stdlib (evita empacotar requests no Lambda)."""

    def send(self, request: HttpRequest) -> HttpResponse:
        req = urllib.request.Request(
            request.url,
            data=request.body,
            headers={'User-Agent': USER_AGENT, **request.headers},
            method=request.method,
        )
        try:
            with urllib.request.urlopen(req, timeout=request.timeout) as resp:
                return HttpResponse(resp.status, resp.read(MAX_BODY_BYTES).decode(errors='replace'))
        except urllib.error.HTTPError as e:
            return HttpResponse(e.code, e.read(MAX_BODY_BYTES).decode(errors='replace'))
