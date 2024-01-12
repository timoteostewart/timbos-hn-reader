import os
import re
import subprocess
import tempfile
import time
import zipfile

import bs4
import requests
import yaml

import config


def download_binary_file(url: str, path: str):
    response = requests.get(url)
    with open(path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def is_a_version_number(s: str) -> bool:
    return bool(re.match(r"^[\d.]+$", s))


def check_for_updated_chromedriver():
    # get system version of /usr/bin/google-chrome-stable
    system_chrome_browser = {}
    output = subprocess.check_output(["google-chrome-stable", "--version"])
    tokens = str(output).split(" ")
    for t in tokens:
        if is_a_version_number(t):
            system_chrome_browser["version"] = t
            break
    system_chrome_browser["major_version"] = int(
        system_chrome_browser["version"].split(".")[0]
    )

    response = requests.get("https://googlechromelabs.github.io/chrome-for-testing/")
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    stable = soup.find("section", {"id": "stable"})
    codes = stable.find_all("code")
    latest_chromedriver = {}
    for c in codes:
        if "chromedriver-linux64.zip" in c.text:
            latest_chromedriver["url"] = c.text

    tokens = latest_chromedriver["url"].split("/")
    for t in tokens:
        if is_a_version_number(t):
            latest_chromedriver["version"] = t
            break

    # check if chromedriver version is already installed
    latest_chromedriver["major_version"] = int(
        latest_chromedriver["version"].split(".")[0]
    )

    installed_chromedrivers_path = "/srv/timbos-hn-reader/bin/chromedriver"

    all_files_and_dirs = os.listdir(installed_chromedrivers_path)
    subdirs = [
        d
        for d in all_files_and_dirs
        if os.path.isdir(os.path.join(installed_chromedrivers_path, d))
    ]
    currently_installed_chromedriver = {}
    currently_installed_chromedriver["version"] = sorted(
        subdirs, key=lambda x: x.split(".")[0]
    )[-1]
    currently_installed_chromedriver["major_version"] = int(
        currently_installed_chromedriver["version"].split(".")[0]
    )

    if (
        system_chrome_browser["major_version"]
        == currently_installed_chromedriver["major_version"]
    ):
        # no need to update chromedriver
        return
    elif system_chrome_browser["major_version"] == latest_chromedriver["major_version"]:
        # update chromedriver
        pass
    else:
        raise Exception(
            f"Cannot reconcile chrome browser and chromedriver versions. system chrome browser version {system_chrome_browser['version']}, currently installed chromedriver version {currently_installed_chromedriver['version']}, latest available chromedriver version {latest_chromedriver['version']}"
        )

    # create target subdirectory
    target_dir = f"{installed_chromedrivers_path}/{latest_chromedriver['version']}"
    try:
        os.makedirs(target_dir)
    except FileExistsError:
        pass

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        # download chromedriver
        download_binary_file(latest_chromedriver["url"], f"{tmp}/chromedriver.zip")
        with zipfile.ZipFile(f"{tmp}/chromedriver.zip", "r") as zip_ref:
            zip_ref.extractall(target_dir)

    new_chromedriver_binary_path = f"{target_dir}/chromedriver-linux64/chromedriver"

    os.chmod(
        new_chromedriver_binary_path,
        os.stat(new_chromedriver_binary_path).st_mode | 0o111,
    )

    # update settings.yaml to point to new chromedriver binary
    with open("/srv/timbos-hn-reader/settings.yaml", "r") as yaml_file:
        data = yaml.safe_load(yaml_file)
    data["SCRAPING"]["PATH_TO_CHROMEDRIVER"] = new_chromedriver_binary_path
    with open("/srv/timbos-hn-reader/settings.yaml", "w") as yaml_file:
        yaml.safe_dump(data, yaml_file, default_flow_style=False)

    config.settings["SCRAPING"]["PATH_TO_CHROMEDRIVER"] = new_chromedriver_binary_path
