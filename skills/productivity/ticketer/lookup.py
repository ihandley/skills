"""Case-insensitive lookup of one config table. First matching key wins."""


def lookup_ci(table, name):
    if not name or not isinstance(table, dict):
        return None
    folded = str(name).casefold()
    for key, value in table.items():
        if str(key).casefold() == folded:
            return value
    return None
