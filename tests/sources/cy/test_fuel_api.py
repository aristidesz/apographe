"""cy.fuel through the official API, offline: the answer is a trimmed copy of the
sample response CY Connect publishes (test data from 2015-2021, not real prices)."""

import gzip
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import pytest

from apographe.core.oauth import ClientCredentials
from apographe.core.source import Options, SourceError
from apographe.core.storage import Store
from apographe.sources.cy.fuel import api
from apographe.sources.cy.fuel.source import FuelSource

SAMPLE = (
    Path(__file__).parents[2] / "fixtures" / "fuel_api" / "response_unleaded95.xml"
).read_text(encoding="utf-8")
SECRET = "s3cr3t-value"
NOW = datetime(2026, 10, 16, 15, 30, 5, tzinfo=ZoneInfo("Asia/Nicosia"))


class Reply:
    def __init__(self, status=200, text="", payload=None):
        self.status_code = status
        self.text = text
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def token_reply(token="tok-1", lifetime=3600):
    return Reply(200, payload={"access_token": token, "expires_in": lifetime})


class Session:
    """Answers each POST with the next scripted reply and keeps the calls."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return self.replies.pop(0)


def clock_from(times):
    it = iter(times)
    return lambda: next(it)


def make_api(token_replies, api_replies, **kw):
    creds = ClientCredentials(
        api.ENVIRONMENTS["sandbox"].token_url,
        "client-1",
        SECRET,
        session=Session(token_replies),
    )
    http = Session(api_replies)
    fuel_api = api.FuelApi(
        api.ENVIRONMENTS["sandbox"],
        creds,
        session=http,
        sleep=lambda s: None,
        **kw,
    )
    return fuel_api, creds, http


# -- reading the answer ---------------------------------------------------


def test_stations_become_rows():
    rows = api.parse_response(SAMPLE, "2026-10-16T15:30:05+03:00", 1)
    assert len(rows) == 5
    first = rows[0]
    assert first["company"] == "ESSO" and first["station_code"] == "ES052"
    assert first["station_name"] == "ΑΔΕΛΦΟΙ ΚΟΥΡΙΔΗ ΛΙΜΙΤΕΔ"  # quotes removed
    assert first["phone"] == "26933657"
    assert first["address"] == "Ευαγόρα Παλληκαρίδη 53 Τ.Κ 8010 τηλ: 26933657"
    assert (first["price"], first["offline"]) == ("1.327", "false")
    assert first["price_changed_at"] == "2018-10-08T06:02:00"
    assert (first["lat"], first["lon"]) == (34.777998, 32.423667)
    assert first["fuel_type_id"] == 1 and first["fuel_type"] == "Αμόλυβδη 95"
    assert set(first) == set(api.FIELDS)


def test_missing_phone_and_coordinates_stay_blank():
    rows = api.parse_response(SAMPLE, "t", 1)
    assert any(r["phone"] == "" for r in rows)
    assert any((r["lat"], r["lon"]) == ("", "") for r in rows)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("34.7779977652251,32.4236665755325", (34.777998, 32.423667)),
        ("34°39'13.5\"N 32°58'26.3\"E", (34.65375, 32.973972)),
        ("", ("", "")),
        ("nonsense", ("", "")),
        ("34°39'13.5\"N", ("", "")),
    ],
)
def test_coordinates_come_in_two_forms(text, expected):
    assert api.coordinates(text) == expected


def test_an_error_answer_is_reported_with_its_code():
    failed = SAMPLE.replace('Success="true" Code="100"', 'Success="false" Code="205"')
    with pytest.raises(SourceError, match="code 205"):
        api.parse_response(failed, "t", 1)


def test_garbage_is_not_xml_we_trust():
    with pytest.raises(SourceError, match="valid XML"):
        api.parse_response("<html>gateway error", "t", 1)
    bomb = '<!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    with pytest.raises(Exception):  # defusedxml refuses entity declarations
        api.parse_response(bomb, "t", 1)


def test_the_request_names_the_fuel_and_is_valid_xml():
    body = api.build_request(3)
    root = ET.fromstring(body)
    node = root.find(".//{http://gateway.gov/schema/mcit/v1}PetroleumType")
    assert node is not None and node.text == "3"


# -- signing in -----------------------------------------------------------


def test_a_token_is_reused_until_it_is_about_to_expire():
    session = Session([token_reply("a", 3600), token_reply("b", 3600)])
    creds = ClientCredentials(
        "https://t.example/token",
        "client-1",
        SECRET,
        session=session,
        clock=clock_from([0, 10, 3540, 3541]),
    )
    assert creds.token() == "a" and creds.token() == "a"
    assert len(session.calls) == 1
    assert creds.token() == "b"  # 3540 s in: inside the one-minute margin
    url, kw = session.calls[0]
    assert kw["auth"] == ("client-1", SECRET)
    assert kw["data"] == {"grant_type": "client_credentials"}


def test_refused_credentials_are_explained_without_showing_the_secret():
    creds = ClientCredentials(
        "https://t.example/token", "client-1", SECRET, session=Session([Reply(401)])
    )
    with pytest.raises(SourceError, match="refused the client id and secret") as e:
        creds.token()
    assert SECRET not in str(e.value) and SECRET not in repr(creds)


def test_settings_come_from_the_environment():
    env, client_id, secret = api.settings_from_env(
        {"CYCONNECT_CLIENT_ID": " id ", "CYCONNECT_CLIENT_SECRET": "sec"}
    )
    assert env.name == "sandbox" and (client_id, secret) == ("id", "sec")
    prod, *_ = api.settings_from_env(
        {
            "CYCONNECT_ENV": "Production",
            "CYCONNECT_CLIENT_ID": "id",
            "CYCONNECT_CLIENT_SECRET": "sec",
        }
    )
    assert prod.name == "production" and prod.folder == "api"
    with pytest.raises(SourceError, match="CYCONNECT_CLIENT_SECRET"):
        api.settings_from_env({"CYCONNECT_CLIENT_ID": "id"})
    with pytest.raises(SourceError, match="'sandbox' or 'production'"):
        api.settings_from_env({"CYCONNECT_ENV": "test"})


# -- calling the API ------------------------------------------------------


def test_a_call_carries_the_token_and_the_xml():
    fuel_api, _, http = make_api([token_reply("tok-1")], [Reply(200, SAMPLE)])
    rows = fuel_api.prices(1, "t")
    assert len(rows) == 5
    url, kw = http.calls[0]
    assert url == api.ENVIRONMENTS["sandbox"].api_url
    assert kw["headers"]["Authorization"] == "Bearer tok-1"
    assert kw["headers"]["Content-Type"] == "application/xml"
    assert b"<PetroleumType>1</PetroleumType>" in kw["data"]


def test_a_refused_token_is_replaced_once():
    fuel_api, creds, http = make_api(
        [token_reply("old"), token_reply("new")],
        [Reply(401), Reply(200, SAMPLE)],
    )
    assert len(fuel_api.prices(1, "t")) == 5
    assert [kw["headers"]["Authorization"] for _, kw in http.calls] == [
        "Bearer old",
        "Bearer new",
    ]


def test_an_application_without_access_is_told_so():
    fuel_api, *_ = make_api(
        [token_reply("a"), token_reply("b")], [Reply(401), Reply(401)]
    )
    with pytest.raises(SourceError, match="approved"):
        fuel_api.prices(1, "t")


def test_server_errors_are_retried():
    slept = []
    fuel_api, _, http = make_api(
        [token_reply()], [Reply(502), Reply(503), Reply(200, SAMPLE)], backoff=10
    )
    fuel_api._sleep = slept.append
    assert len(fuel_api.prices(1, "t")) == 5
    assert len(http.calls) == 3 and slept == [10, 20]


def test_giving_up_says_why():
    fuel_api, *_ = make_api([token_reply()], [Reply(502)] * 4)
    with pytest.raises(SourceError, match="failed 4 times: HTTP 502"):
        fuel_api.prices(1, "t")


# -- the job --------------------------------------------------------------


def run(fuel_api, tmp_path, **kw):
    source = FuelSource(fuel_api=fuel_api, clock=lambda: NOW)
    out = Store(tmp_path).scope(source.folder)
    report = source.run("api", out, Options(day=NOW.date(), **kw))
    return out, report


def test_the_job_writes_one_file_per_run(tmp_path):
    fuel_api, *_ = make_api([token_reply()], [Reply(200, SAMPLE)] * 5)
    out, report = run(fuel_api, tmp_path)
    assert report.rows == {"prices": 25}  # 5 fuels x 5 sample stations
    path = "api-sandbox/2026/prices_2026-10-16_1530.csv.gz"
    assert out.exists(path)
    with gzip.open(out.path(path), "rt", encoding="utf-8") as fh:
        header = fh.readline().strip()
    assert header == ",".join(api.FIELDS)
    rows = out.read_csv(path)
    assert {r["fuel_type_id"] for r in rows} == {"1", "2", "3", "4", "5"}
    assert rows[0]["fetched_at"] == "2026-10-16T15:30:05+03:00"
    assert len(fuel_api.session.calls) == 5  # one token, five fuels


def test_only_picks_fuels(tmp_path):
    fuel_api, _, http = make_api([token_reply()], [Reply(200, SAMPLE)])
    _, report = run(fuel_api, tmp_path, only=["3"])
    assert report.rows == {"prices": 5} and len(http.calls) == 1


@pytest.mark.parametrize("only", [["9"], ["diesel"]])
def test_unknown_fuels_are_refused(tmp_path, only):
    fuel_api, *_ = make_api([], [])
    with pytest.raises(SourceError, match="fuel type"):
        run(fuel_api, tmp_path, only=only)


def test_without_credentials_the_job_says_what_to_set(tmp_path, monkeypatch):
    for name in ("CYCONNECT_CLIENT_ID", "CYCONNECT_CLIENT_SECRET", "CYCONNECT_ENV"):
        monkeypatch.delenv(name, raising=False)
    source = FuelSource(clock=lambda: NOW)
    with pytest.raises(SourceError, match="CYCONNECT_CLIENT_ID"):
        source.run("api", Store(tmp_path), Options(day=NOW.date()))
