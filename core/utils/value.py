def safe_int(value: str) -> int:
    try:
        return int(value)
    except e:
        print(e)
        return 0