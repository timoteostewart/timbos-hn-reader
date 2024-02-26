import requests


def download_file(url, dest_local_file, log_prefix="") -> bool:
    log_prefix_local = log_prefix + "download_file(): "
    try:
        with requests.get(url, stream=True) as response:
            if response and response.status_code == 200:
                with open(dest_local_file, "wb") as fout:
                    for chunk in response.iter_content(chunk_size=8192):
                        fout.write(chunk)
                return True
            else:
                print(
                    f"{log_prefix_local}Error: Server responded with status code {response=}"
                )
                return False
    except Exception as exc:
        print(f"{log_prefix_local}Exception occurred: {exc}")
        return False


download_file("https://www.timstewart.io/lipsum.html", "lipsum.html")
download_file("https://www.hayfevr.ly/images/hf.webp", "hf.webp")
