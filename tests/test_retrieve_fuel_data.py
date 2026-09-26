import pytest

from fuel_prices.retrieve_fuel_data import extract_station_table


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    # extract_station_table calls time.sleep(2) twice; neutralise it so the
    # pure-parsing tests run instantly and deterministically.
    monkeypatch.setattr("fuel_prices.retrieve_fuel_data.time.sleep", lambda *_: None)


def _station_html(brand, address, area, price):
    """Build one main row (with the address link) plus its detail row.

    Mirrors the real page: the main row carries ``data-expanded`` and the
    price/brand cells, while the following sibling row holds the area inside
    a nested table cell styled ``display: table-cell;``.
    """
    return f"""
      <tr data-expanded="true">
        <td>{brand}</td>
        <td>logo</td>
        <td><a href="#">{address}</a></td>
        <td>map</td>
        <td>{price}</td>
      </tr>
      <tr>
        <td>
          <table>
            <tr><td style="display: table-cell;">{area}</td></tr>
          </table>
        </td>
      </tr>
    """


def _page(*rows):
    body = "".join(rows)
    return f"""
    <html><body>
      <table id="petroleumPriceDetailsFootable">
        <tbody>{body}</tbody>
      </table>
    </body></html>
    """


def test_parses_each_station_into_a_row():
    html = _page(
        _station_html("ESSO", "Καντάρας 58", "Καϊμακλί", "1,467"),
        _station_html("EKO", "Λεωφ. Στροβόλου 10", "Στρόβολος", "1,489"),
    )

    df = extract_station_table(html)

    assert list(df.columns) == ["brand", "address", "area", "price"]
    assert len(df) == 2
    assert df.iloc[0].to_dict() == {
        "brand": "ESSO",
        "address": "Καντάρας 58",
        "area": "Καϊμακλί",
        "price": "1.467",
    }
    assert df.iloc[1]["brand"] == "EKO"
    assert df.iloc[1]["area"] == "Στρόβολος"


def test_price_comma_is_normalised_to_a_dot():
    # The site formats prices with a decimal comma; downstream code expects a dot.
    html = _page(_station_html("ESSO", "addr", "area", "1,999"))

    df = extract_station_table(html)

    assert df.iloc[0]["price"] == "1.999"


def test_missing_table_returns_empty_dataframe():
    df = extract_station_table("<html><body>no table here</body></html>")

    assert df.empty


def test_detail_rows_are_not_parsed_as_stations():
    # Two stations => four <tr> total (2 main + 2 detail). Only the two main
    # rows (data-expanded) should become records.
    html = _page(
        _station_html("ESSO", "a1", "area1", "1,100"),
        _station_html("EKO", "a2", "area2", "1,200"),
    )

    df = extract_station_table(html)

    assert len(df) == 2
