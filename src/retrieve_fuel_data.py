import time

import chromedriver_autoinstaller
import pandas as pd
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


def extract_station_table(html):
    time.sleep(2)
    soup = BeautifulSoup(html, "html.parser")
    time.sleep(2)
    table = soup.find("table", id="petroleumPriceDetailsFootable")
    if not table:
        print("Table not found")
        return pd.DataFrame()
    tbody = table.find("tbody")
    rows = tbody.find_all("tr", recursive=False)
    data = []
    i = 0
    while i < len(rows):
        row = rows[i]
        if row.has_attr("data-expanded"):
            cells = row.find_all("td", recursive=False)
            # Brand
            brand = cells[0].get_text(strip=True).replace("\n", "").replace("\r", "")
            # Address
            address_link = cells[2].find("a")
            address = (
                address_link.get_text(separator="\n", strip=True)
                if address_link
                else ""
            )
            # Price
            price = cells[4].get_text(strip=True).replace(",", ".")
            # Area (from next detail row)
            area = ""
            if i + 1 < len(rows):
                detail_row = rows[i + 1]
                area_td = detail_row.find("td")
                if area_td:
                    area_table = area_td.find("table")
                    if area_table:
                        area_cell = area_table.find("td", style="display: table-cell;")
                        area = area_cell.get_text(strip=True) if area_cell else ""
            data.append(
                {"brand": brand, "address": address, "area": area, "price": price}
            )
            i += 2  # Skip to next main row
        else:
            i += 1
    return pd.DataFrame(data)


def click_ok_button(driver):
    # Wait for the OK button to appear and click it
    try:
        ok_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-bb-handler='ok']"))
        )
        ok_button.click()
        print("Clicked OK button")
    except Exception as e:
        print("OK button not found or not clickable:", e)


def download_petroleum_prices():
    display = Display(visible=0, size=(1200, 1200))
    display.start()

    chromedriver_autoinstaller.install()

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1200,1200")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")

    driver = webdriver.Chrome(options=chrome_options)

    driver.set_window_size(550, 691)
    all_data = []

    try:
        driver.get("https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "Entity_PetroleumType"))
        )
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "Entity_PetroleumType"))
        )
        time.sleep(5)
        click_ok_button(driver)
        # time.sleep(5)
        fuel_select = Select(driver.find_element(By.ID, "Entity_PetroleumType"))
        fuel_options = [
            {"value": opt.get_attribute("value"), "text": opt.text.strip()}
            for opt in fuel_select.options
            if opt.get_attribute("value")
        ]

        for fuel in fuel_options:
            print(f"Processing: {fuel['text']}")

            fuel_select.select_by_value(fuel["value"])
            # time.sleep(2)
            submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
            driver.execute_script("arguments[0].scrollIntoView();", submit_button)
            submit_button.click()

            wait = WebDriverWait(driver, 15)
            table_locator = (By.ID, "petroleumPriceDetailsFootable")
            wait.until(EC.presence_of_element_located(table_locator))
            wait = WebDriverWait(driver, 15)
            first_row_locator = (
                By.XPATH,
                "//table[@id='petroleumPriceDetailsFootable']/tbody/tr",
            )
            time.sleep(2)
            wait.until(EC.presence_of_element_located(first_row_locator))
            df = extract_station_table(driver.page_source)
            if not df.empty:
                print(df.head())
            else:
                print(f"No data found for {fuel['text']}")
                continue
            df["fuel_type"] = fuel["text"]
            df["datetime"] = pd.to_datetime("today")
            all_data.append(df)
            time.sleep(2)
            driver.get(
                "https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices"
            )
            time.sleep(2)
            click_ok_button(driver)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "Entity_PetroleumType"))
            )
            fuel_select = Select(driver.find_element(By.ID, "Entity_PetroleumType"))
        df_all = pd.concat(all_data, ignore_index=True)
        return df_all
    finally:
        driver.quit()


def run():
    df = download_petroleum_prices()
    fuel_types = [
        "Αμόλυβδη 95",
        "Πετρέλαιο κίνησης",
        "Αμόλυβδη 98",
        "Κηροζίνη",
        "Πετρέλαιο Θέρμανσης",
    ]
    found_types = set(df["fuel_type"].unique())
    expected_set = set(fuel_types)
    missing_types = expected_set - found_types
    if missing_types:
        print(f"Validation failed. Missing fuel types: {', '.join(missing_types)}")
    else:
        print("All fuel types are present.")
    df.to_csv(f"data/fuel_prices_{pd.to_datetime('today').date()}.csv", index=False)
