import hashlib, os, time, subprocess

def sha256_cpu(iters: int, payload: dict) -> dict:
    # create file to store hashes in
    hash_file = "hashdb.bin"
    flush_threshold = 256 * 1024  # keep disk writes infrequent
    buffer = bytearray()
    # hash a fixed 1KB buffer iters times (CPU-bound placeholder)
    # generate a new 1KB random buffer each iteration for unique digests
    h = hashlib.sha256
    with open(hash_file, "wb") as f:
        for _ in range(iters):
            buf = os.urandom(1024)  # 1KB random data
            digest = h(buf).hexdigest().encode("ascii")
            buffer.extend(digest)
            buffer.append(10)  # newline.
            if len(buffer) >= flush_threshold:
                f.write(buffer)
                buffer.clear()
        if buffer:
            f.write(buffer)

    return {"done": iters}

def sleep_us(iters: int, payload: dict) -> dict:
    # Simulate device latency
    micros = int(payload.get("micros", 1000))
    dur = micros / 1_000_000
    for _ in range(iters):
        time.sleep(dur)
    return {"done": iters}
    

# ctypes/cffi wrapper (pseudo-replace with a binding)
# from my_atecc import atecc_sha256, atecc_random
# def op_attec_sha256(data: bytes) -> str:
#     return atecc_sha256(data)

OPS = {
    "sha256_cpu": sha256_cpu,
    "sleep_us": sleep_us,
    #"atecc_sha256": op_atecc_sha256,
}