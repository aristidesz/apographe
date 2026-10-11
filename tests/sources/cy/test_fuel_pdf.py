from datetime import datetime, timezone
from pathlib import Path

import pytest

from apographe.sources.cy.fuel import pdf as conv

BRANDS = {"ESSO", "ENI", "TOTAL PLUS", "ΑΝΕΞΑΡΤΗΤΟ ΠΡΑΤΗΡΙΟ", "JACKOSON"}


def test_a_plain_row_and_its_phone():
    lines = ["ESSO Καντάρας 58 Τ.Κ 1037 Καϊμακλί 1,519", "τηλ: 22433430"]
    assert conv.parse_stations(lines, BRANDS) == [
        conv.Station("ESSO", "Καντάρας 58 Τ.Κ 1037 Καϊμακλί", "1,519", "22433430")
    ]


def test_a_two_word_brand_that_wraps():
    lines = [
        "TOTAL Λεωφ.Αφροδίτης 21 Τ.Κ 8270 Τρεμιθούσα 1,578",
        "PLUS τηλ: 26654694",
    ]
    [s] = conv.parse_stations(lines, BRANDS)
    assert (s.brand, s.phone) == ("TOTAL PLUS", "26654694")


def test_a_long_address_puts_the_phone_one_line_later():
    lines = [
        "ENI Λεωφ. Αμμοχώστου (Δρόμος Λάρνακας- Δρόμος Λάρνακας - 2,058",
        "Δεκέλειας) Τ.Κ 6019 Δεκέλειας",
        "τηλ: 24632200",
        "ESSO Καντάρας 58 Τ.Κ 1037 Καϊμακλί 1,519",
    ]
    stations = conv.parse_stations(lines, BRANDS)
    assert [s.phone for s in stations] == ["24632200", None]


def test_header_lines_are_not_stations():
    lines = ["Μέση Τιμή σε € (Παγκύπρια) 1,535", "Σήμα Διεύθυνση Περιοχή/Χωριό Τιμή"]
    assert conv.parse_stations(lines, BRANDS) == []


def test_a_station_keeps_the_scrapers_spelling():
    known = {("ESSO", "22433430"): ("Καντάρας 58 Τ.Κ 1037\n τηλ: 22433430", "Καϊμακλί")}
    s = conv.Station("ESSO", "Καντάρας 58 Τ.Κ 1037 Καϊμακλί", "1,519", "22433430")
    assert conv.match(s, known, {}) == known[("ESSO", "22433430")]


def test_a_station_without_a_phone_matches_on_area_and_address():
    nophone = {"JACKOSON": {("", "Αγρός"): 0}}
    s = conv.Station(
        "JACKOSON", "Δρόμος Παλαιχωρίου - Αγρού Τ.Κ 4860 Αγρός", "1,727", None
    )
    assert conv.match(s, {}, nophone) == ("", "Αγρός")


def test_an_unknown_station_stops_the_run():
    s = conv.Station("ESSO", "Νέος δρόμος 1 Πουθενά", "1,500", "99999999")
    with pytest.raises(LookupError):
        conv.match(s, {}, {})


def test_fuel_names_follow_the_scraper_not_the_page():
    assert conv.canonical_fuel("Πετρέλαιο Κίνησης") == "Πετρέλαιο κίνησης"
    assert conv.canonical_fuel("Πετρέλαιο θέρμανσης") == "Πετρέλαιο Θέρμανσης"
    with pytest.raises(ValueError):
        conv.canonical_fuel("Υγραέριο")


def test_the_pages_own_figures_must_match():
    conv.check_header("Κηροζίνη", [1.5, 1.4, 1.6], [1.4, 1.5, 1.6])
    with pytest.raises(ValueError):
        conv.check_header("Κηροζίνη", [1.5, 1.4, 1.6], [1.4, 1.4])


def test_creation_time_is_utc():
    expected = datetime(2026, 10, 2, 5, 49, 1, tzinfo=timezone.utc)
    assert conv.pdf_created({"CreationDate": "D:20261002054901Z00'00'"}) == expected
    assert conv.pdf_created({}) is None


def test_a_station_whose_text_changed_takes_the_latest_spelling():
    nophone = {
        "EKO": {
            ("Κάτω Πύργος", "Κάτω Πύργος"): 3,
            ("Κάτω Πύργος Τ.Κ 2940", "Κάτω Πύργος"): 9,
        }
    }
    s = conv.Station("EKO", "Κάτω Πύργος Τ.Κ 2940 Κάτω Πύργος", "1,769", None)
    assert conv.match(s, {}, nophone) == ("Κάτω Πύργος Τ.Κ 2940", "Κάτω Πύργος")


def _page(fuel, minute, day=1):
    when = datetime(2026, 10, day, 16, minute, tzinfo=timezone.utc)
    return conv.Page(Path(f"{fuel}-{day}.pdf"), fuel, when, "")


def test_a_folder_of_two_days_gives_two_snapshots():
    day1 = [_page(f, i) for i, f in enumerate(conv.FUEL_TYPES)]
    day2 = [_page(f, i, day=2) for i, f in enumerate(conv.FUEL_TYPES)]
    groups = conv.snapshots(day2 + day1)
    assert [[p.path.name for p in g] for g in groups] == [
        [p.path.name for p in day1],
        [p.path.name for p in day2],
    ]


def test_the_same_fuel_twice_starts_a_new_snapshot():
    groups = conv.snapshots([_page("Κηροζίνη", 0), _page("Κηροζίνη", 2)])
    assert len(groups) == 2
