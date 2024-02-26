import hashlib
import time
import zlib


def get_crc32_of_string(string, length=12):
    # quick but not cryptographically secure 32-bit hash
    string_as_bytes = string.encode("utf-8")
    crc32_hash = zlib.crc32(string_as_bytes)
    crc32_hash &= 0xFFFFFFFF  # ensure hash is a positive number
    return str(crc32_hash)[:length]


def get_hash_of_url(url, length=12):
    return get_crc32_of_string(url, length)


def get_sha1_of_bytes(bytes):
    # 160-bit hash
    hf = hashlib.sha1()
    hf.update(bytes)
    return str(hf.hexdigest())


def get_sha1_of_current_time(length=12):
    time_as_string = str(time.time()).replace(".", "")
    time_as_bytes = str(time_as_string).encode("utf-8")
    return get_sha1_of_bytes(time_as_bytes)[:length]


def get_sha1_of_string(string: str, length=12):
    string_as_bytes = string.encode("utf-8")
    return get_sha1_of_bytes(string_as_bytes)[:length]
