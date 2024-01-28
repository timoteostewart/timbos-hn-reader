import time

import requests

# monkey patch hrequests to reduce crashing
fingerprints_bablosoft_com_responses = {}


def endpoint_query_via_requests(url=None, retries=3, delay=60, log_prefix=""):
    if retries == 0:
        # logger.error(log_prefix + f"GET request {url} failed")
        # raise FailedAfterRetrying()
        exit(1)

    try:
        resp = requests.get(url)
        resp.raise_for_status()
        resp_as_json = resp.json()
        # logger.info(log_prefix + f"successfully queried endpoint {url}")
        return resp_as_json
    except Exception as exc:
        # logger.warning(
        #     log_prefix
        #     + f"problem querying {url}: {exc} ; will delay {delay} seconds and try again ; retries left {retries}"
        # )
        time.sleep(delay)

        return endpoint_query_via_requests(
            url=url, retries=retries - 1, delay=delay * 2, log_prefix=log_prefix
        )


def populate_fingerprints_bablosoft_com_responses():
    for browser_name in [
        "chrome",
        "chromium",
        "edge",
        "firefox",
        "safari",
    ]:
        url = f"http://fingerprints.bablosoft.com/preview?rand=0.1&tags={browser_name},Desktop,Microsoft%20Windows"
        fingerprints_bablosoft_com_responses[
            browser_name
        ] = endpoint_query_via_requests(url=url)


if __name__ == "__main__":
    my_wan_ip = endpoint_query_via_requests(
        url="https://api.ipify.org?format=json", retries=10, delay=2, log_prefix=""
    )
    print(my_wan_ip)
