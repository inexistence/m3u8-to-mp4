def safe_int(value: str) -> int:
    try:
        return int(value)
    except Exception as e:
        print(e)
        return 0