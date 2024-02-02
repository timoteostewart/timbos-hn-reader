import hashlib
import time
import zlib


def get_sha1_of_current_time(length=12):
    hf = hashlib.sha1()
    t = time.time()
    t_bytes = str(t).encode("utf-8")
    hf.update(t_bytes)
    return str(hf.hexdigest())[:length]


def get_sha1_of_string(string, length=12):
    hf = hashlib.sha1()
    t = time.time()
    t_bytes = str(t).encode("utf-8")
    hf.update(t_bytes)
    return str(hf.hexdigest())[:length]


def get_crc32_of_string(string, length=12):
    crc32_hash = zlib.crc32(string.encode())
    crc32_hash &= 0xFFFFFFFF
    return str(crc32_hash)[:length]

def get_hash_of_url(url, length=12):
    return get_crc32_of_string(url, length)
