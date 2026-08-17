import time
import functools


def execution_logger(func):
    """Decorator that logs how long the wrapped function took to run."""
    @functools.wraps(func)  # preserves __name__, __doc__, __module__, etc.
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # runs even if func raises, so timing is always logged
            elapsed = time.perf_counter() - start
            print(f"[execution_logger] {func.__name__} took {elapsed:.6f}s")
    return wrapper


def read_large_file(file_path, chunk_size=8192):
   
    leftover = ""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            leftover += chunk
            lines = leftover.split("\n")
            leftover = lines.pop()  # last piece may be incomplete, keep it
            for line in lines:
                yield line
        if leftover:
            yield leftover


@execution_logger
def process_log_file(file_path, keyword=None):
    
    count = 0
    for line in read_large_file(file_path):
        if keyword is None or keyword in line:
            count += 1
    return count


if __name__ == "__main__":
    # Example usage:
    # total = process_log_file("massive_10gb_log.txt", keyword="ERROR")
    # print(f"Matching lines: {total}")

    # Small demo with a temp file so this runs standalone
    import tempfile, os

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as tmp:
        for i in range(100_000):
            tmp.write(f"line {i} - INFO - some log message\n")
        tmp_path = tmp.name

    total = process_log_file(tmp_path, keyword="INFO")
    print(f"Matching lines: {total}")

    os.remove(tmp_path)