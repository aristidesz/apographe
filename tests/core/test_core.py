import requests

from apographe import cli
from apographe.core.http import PoliteClient
from apographe.core.source import LoginWall, SourceError
from apographe.core.storage import Store


class Response:
    def __init__(self, status=200, payload=None, url="https://example.org/api/x"):
        self.status_code = status
        self._payload = payload
        self.url = url
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class Session(requests.Session):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, **kw):
        self.calls += 1
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def client(responses, slept=None):
    clock = iter(range(0, 10_000, 1))
    return PoliteClient(
        "https://example.org/api",
        min_interval=3,
        backoff=10,
        retries=2,
        session=Session(responses),
        sleep=(slept.append if slept is not None else (lambda s: None)),
        clock=lambda: float(next(clock)),
    )


def test_server_errors_are_retried_with_backoff():
    slept = []
    c = client([Response(502), requests.Timeout(), Response(200, {"ok": 1})], slept)
    assert c.get_json("/x") == {"ok": 1}
    assert c.session.calls == 3
    assert 10 in slept and 20 in slept  # backoff grows per attempt


def test_requests_are_spaced_out():
    slept = []
    c = client([Response(200, []), Response(200, [])], slept)
    c.get_json("/x")
    c.get_json("/x")
    assert slept == [2.0]  # 3 s apart, 1 s already passed on the fake clock


def test_a_login_page_stops_the_run():
    for answer in (
        Response(401),
        Response(200, {}, url="https://login.example.gov/auth?next=x"),
    ):
        c = client([answer])
        try:
            c.get_json("/x")
        except LoginWall:
            pass
        else:
            raise AssertionError("expected LoginWall")


def test_giving_up_says_why():
    c = client([Response(502)] * 3)
    try:
        c.get_json("/x")
    except SourceError as exc:
        assert "failed 3 times: HTTP 502" in str(exc)
    else:
        raise AssertionError("expected SourceError")


def test_gzip_output_is_byte_identical_on_rerun(tmp_path):
    store = Store(tmp_path)
    rows = [{"a": 1, "b": "Λεμεσός"}]
    path, count = store.write_csv("t/x.csv.gz", rows, ["a", "b"])
    first = path.read_bytes()
    store.write_csv("t/x.csv.gz", rows, ["a", "b"])
    assert count == 1 and path.read_bytes() == first
    assert store.read_csv("t/x.csv.gz") == [{"a": "1", "b": "Λεμεσός"}]
    assert not list(tmp_path.rglob(".*.tmp"))


def test_cli_lists_sources_and_rejects_unknown_jobs(capsys):
    assert cli.main(["list"]) == 0
    assert "cy.ekalathi" in capsys.readouterr().out
    assert cli.main(["run", "cy.ekalathi", "--job", "nope"]) == 1
    assert cli.main(["run", "xx.nothing"]) == 1
