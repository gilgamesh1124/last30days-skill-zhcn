"""WBI signature helpers for Bilibili web APIs.

Pure-function module — no HTTP, no global state. The 64-byte permutation
table (MIXIN_KEY_ENC_TAB) is the documented Bilibili-public constant from
SocialSisterYi/bilibili-API-collect (docs/misc/sign/wbi.md). It maps
positions in (img_key + sub_key) onto positions in the 32-char mixin_key.
"""

import hashlib
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

# Source: github.com/SocialSisterYi/bilibili-API-collect/docs/misc/sign/wbi.md
# If signing breaks (e.g. /search returns code=-352 with v_voucher), re-verify
# this table against the upstream doc before changing the algorithm.
MIXIN_KEY_ENC_TAB: List[int] = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def get_wbi_keys(nav_json: Dict[str, Any]) -> Tuple[str, str]:
    """Extract (img_key, sub_key) from a /x/web-interface/nav response.

    The keys are the basename-without-extension of img_url and sub_url.
    Raises ValueError if the response shape is unexpected or URLs are
    not the expected `.../wbi/<hex>.png` form.
    """
    try:
        wbi = nav_json["data"]["wbi_img"]
        img_url = wbi["img_url"]
        sub_url = wbi["sub_url"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"nav_json missing wbi_img keys: {exc}") from exc

    img_key = _basename_no_ext(img_url)
    sub_key = _basename_no_ext(sub_url)
    if not img_key or not sub_key:
        raise ValueError(f"malformed wbi urls: img={img_url!r} sub={sub_url!r}")
    return img_key, sub_key


def _basename_no_ext(url: str) -> str:
    """Return 'abc123' from 'https://example/path/abc123.png'."""
    if not isinstance(url, str) or "/" not in url:
        return ""
    tail = url.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0] if "." in tail else tail


def mix_key(img_key: str, sub_key: str) -> str:
    """Permute (img_key + sub_key) by MIXIN_KEY_ENC_TAB, truncate to 32 chars."""
    combined = img_key + sub_key
    return "".join(combined[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign_params(
    params: Dict[str, Any],
    mixin_key: str,
    *,
    ts: Optional[int] = None,
) -> Dict[str, Any]:
    """Return a new params dict with `wts` and `w_rid` added.

    Algorithm (per SocialSisterYi/bilibili-API-collect wbi.md):
      1. wts = int(time.time()) unless `ts` is injected (test seam).
      2. Sort the union of params and {wts}, URL-encode each value.
      3. Join as k1=v1&k2=v2&...
      4. Append mixin_key, MD5, hex-digest -> w_rid.

    Args:
        params: caller's request parameters. Not mutated.
        mixin_key: 32-char key from mix_key().
        ts: optional Unix timestamp override (used in tests).

    Returns:
        New dict containing all original params plus wts and w_rid.
    """
    if ts is None:
        ts = int(time.time())

    signed = dict(params)
    signed["wts"] = ts

    query = urllib.parse.urlencode(sorted(signed.items()))
    signed["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return signed
