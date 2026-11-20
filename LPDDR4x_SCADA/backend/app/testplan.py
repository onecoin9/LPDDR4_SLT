"""Screening presets and ordered selection. Mask bit identities never change."""
from .cfg import _P2_BIT_BY_NAME

MODES = ("快速筛查", "完整筛查", "坏区管理")
ALL_ALGORITHMS = tuple(sorted(_P2_BIT_BY_NAME, key=lambda n: min(_P2_BIT_BY_NAME[n])))
QUICK_ALGORITHMS = (
    "test_seqinc_comparison", "test_random_value", "test_march_c_comparison",
    "test_run_moving_inv", "test_ac_graycode",
)
# These expected-value scans record each failing region. March sequences retain
# their existing continued checks; other scans continue via mt_check_word.
BAD_AREA_ALGORITHMS = (
    "test_march_c_comparison", "test_run_moving_inv", "test_ac_march_c",
    "test_ac_march_la", "test_ac_graycode", "test_ac_rc_frame_march_raw",
)


def ordered_algorithms(pl2, names):
    orders = pl2.get("executionOrder", {})
    if not isinstance(orders, dict):
        raise ValueError("executionOrder must be an object")
    ranked, used = [], set()
    for name in names:
        value = orders.get(name, min(_P2_BIT_BY_NAME[name]) + 1)
        if isinstance(value, bool) or not str(value).isdigit() or not 1 <= int(value) <= 9999:
            raise ValueError("order must be an integer from 1 to 9999")
        value = int(value)
        if value in used:
            raise ValueError("selected algorithms must have distinct order numbers")
        used.add(value)
        ranked.append((value, name))
    direction = pl2.get("ascOrder", "升序") if "executionOrder" in pl2 else "升序"
    if direction not in ("升序", "降序"):
        raise ValueError("invalid order direction")
    return [name for _, name in sorted(ranked, reverse=direction == "降序")]
