
# Shared by both domains and holds no domain knowledge. All math and all
# comparisons happen in integer mm; cm exists only at the form/display edge.

from decimal import Decimal, InvalidOperation
 
 
def cm_to_mm(measurement):
    """Parse a cm value typed into a form ("52.5") into integer mm (525)."""
    try:
        value = Decimal(str(measurement).strip())
    except InvalidOperation:
        raise ValueError(f"{measurement!r} is not a number") from None
    if not value.is_finite():
        raise ValueError(f"{measurement!r} is not a number")
    mm = value * 10
    if mm != mm.to_integral_value():
        raise ValueError(f"{measurement!r} is more precise than 1 mm")
    return int(mm)
 
 
def mm_to_cm(mm):
    """Format integer mm for display: 525 -> "52.5", 520 -> "52.0"."""
    return f"{mm / 10:.1f}"