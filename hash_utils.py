import hashlib
import time


def get_sha1_of_current_time():
    hf = hashlib.sha1()
    t = time.time()
    t_bytes = str(t).encode("utf-8")
    hf.update(t_bytes)
    return str(hf.hexdigest())[:12]
