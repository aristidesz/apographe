from datetime import datetime, timezone

import pytest

from fuel_prices.pdf_to_csv import (
    Station,
    canonical_fuel,
    check_header,
    match,
    parse_stations,
    pdf_created,
)

BRANDS = {"ESSO", "ENI", "TOTAL PLUS", "ΑΝΕΞΑΡΤΗΤΟ ΠΡΑΤΗΡΙΟ", "JACKOSON"}


def test_a_plain_row_and_its_phone():
    lines = ["ESSO Καντάρας 58 Τ.Κ 1037 Καϊμακλί 1,519", "τηλ: 22433430"]
    assert parse_stations(lines, BRANDS) == [
        Station("ESSO", "Καντάρας 58 Τ.Κ 1037 Καϊμακλί", "1,519", "22433430")
    ]


def test_a_two_word_brand_that_wraps():
    lines = [
        "TOTAL Λεωφ.Αφροδίτης 21 Τ.Κ 8270 Τρεμιθούσα 1,578",
        "PLUS τηλ: 26654694",
    ]
    [s] = parse_stations(lines, BRANDS)
    assert (s.brand, s.phone) == ("TOTAL PLUS", "26654694")


def test_a_long_address_puts_the_phone_one_line_later():
    lines = [
        "ENI Λεωφ. Αμμοχώστου (Δρόμος Λάρνακας- Δρόμος Λάρνακας - 2,058",
        "Δεκέλειας) Τ.Κ 6019 Δεκέλειας",
        "τηλ: 24632200",
        "ESSO Καντάρας 58 Τ.Κ 1037 Καϊμακλί 1,519",
    ]
    stations = parse_stations(lines, BRANDS)
    assert [s.phone for s in stations] == ["24632200", None]


def test_header_lines_are_not_stations():
    lines = ["Μέση Τιμή σε € (Παγκύπρια) 1,535", "Σήμα Διεύθυνση Περιοχή/Χωριό Τιμή"]
    assert parse_stations(lines, BRANDS) == []


def test_a_station_keeps_the_scrapers_spelling():
    known = {("ESSO", "22433430"): ("Καντάρας 58 Τ.Κ 1037\n τηλ: 22433430", "Καϊμακλί")}
    s = Station("ESSO", "Καντάρας 58 Τ.Κ 1037 Καϊμακλί", "1,519", "22433430")
    assert match(s, known, {}) == known[("ESSO", "22433430")]


def test_a_station_without_a_phone_matches_on_area_and_address():
    nophone = {"JACKOSON": {("", "Αγρός"): 0}}
    s = Station("JACKOSON", "Δρόμος Παλαιχωρίου - Αγρού Τ.Κ 4860 Αγρός", "1,727", None)
    assert match(s, {}, nophone) == ("", "Αγρός")


def test_an_unknown_station_stops_the_run():
    s = Station("ESSO", "Νέος δρόμος 1 Πουθενά", "1,500", "99999999")
    with pytest.raises(LookupError):
        match(s, {}, {})


def test_fuel_names_follow_the_scraper_not_the_page():
    assert canonical_fuel("Πετρέλαιο Κίνησης") == "Πετρέλαιο κίνησης"
    assert canonical_fuel("Πετρέλαιο θέρμανσης") == "Πετρέλαιο Θέρμανσης"
    with pytest.raises(ValueError):
        canonical_fuel("Υγραέριο")


def test_the_pages_own_figures_must_match():
    check_header("Κηροζίνη", [1.5, 1.4, 1.6], [1.4, 1.5, 1.6])
    with pytest.raises(ValueError):
        check_header("Κηροζίνη", [1.5, 1.4, 1.6], [1.4, 1.4])


def test_creation_time_is_utc():
    expected = datetime(2026, 10, 2, 5, 49, 1, tzinfo=timezone.utc)
    assert pdf_created({"CreationDate": "D:20261002054901Z00'00'"}) == expected
    assert pdf_created({}) is None


def test_a_station_whose_text_changed_takes_the_latest_spelling():
    nophone = {
        "EKO": {
            ("Κάτω Πύργος", "Κάτω Πύργος"): 3,
            ("Κάτω Πύργος Τ.Κ 2940", "Κάτω Πύργος"): 9,
        }
    }
    s = Station("EKO", "Κάτω Πύργος Τ.Κ 2940 Κάτω Πύργος", "1,769", None)
    assert match(s, {}, nophone) == ("Κάτω Πύργος Τ.Κ 2940", "Κάτω Πύργος")
