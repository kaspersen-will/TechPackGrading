
# Pure grading logic. All values are integer mm, so every sum is exact.

class GradingError(ValueError):
    # Raised when grading fails due to missing or invalid data.
    pass


def validate_size_run(sizes, base_size):
    if not sizes:
        raise GradingError("a size run needs at least one size")
    if len(set(sizes)) != len(sizes):
        raise GradingError("a size run can't list the same size twice")
    if base_size not in sizes:
        raise GradingError(f"base size {base_size!r} is not in the size run")
    if any(not size.strip() for size in sizes):
        raise GradingError("a size label can't be blank")


def grade(base_value_mm, base_position, target_position, increments):
    # Return one point of measure's value at target_position, in mm.
    value = base_value_mm
    if target_position > base_position:
        for position in range(base_position + 1, target_position + 1):
            value += _increment(increments, position)
    else:
        for position in range(target_position + 1, base_position + 1):
            value -= _increment(increments, position)
    return value


def _increment(increments, position):
    if position not in increments:
        raise GradingError(f"missing grade rule for size position {position}")
    return increments[position]