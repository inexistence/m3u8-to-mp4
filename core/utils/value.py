def safe_int(value: str) -> int:
    try:
        return int(value)
    except Exception as e:
        print(e)
        return 0
    
def get_value(dict: dict, key: str, default_value):
    return dict[key] if key in dict else default_value