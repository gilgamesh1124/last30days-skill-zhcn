# Bilibili Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Bilibili (B站) as a first-class web source in the last30days skill via a single upstream PR composed of 4 atomic commits.

**Architecture:** Mirror the existing `xiaohongshu_api.py` adapter pattern. Two new files — `bilibili.py` (search adapter + cookie bootstrap) and `bilibili_wbi.py` (pure-function WBI signing) — plus minimal registration edits in 7 existing modules. All tests are fixture-based, no live network in CI. Cookie bootstrap uses `urllib` directly because the project's `http.py` does not expose response headers.

**Tech Stack:** Python 3.10+, standard library only (`urllib`, `hashlib`, `time`, `json`); reuses project's `http.py` for the search call; `pytest` for tests; `unittest.mock.patch` for HTTP mocking.

**Repo root:** `E:/codexworkplace/projects/last30days-skill-zhcn`
**Working branch:** `feat/bilibili-adapter` (off `main`)

---

## Reference: Spec

This plan implements `docs/superpowers/specs/2026-06-08-bilibili-adapter-design.md`. Read it once before starting.

---

## Phase 0: Branch Setup

### Task 0: Create feature branch

**Files:** none

- [ ] **Step 1: Verify clean working tree on main**

Run from repo root:
```bash
cd E:/codexworkplace/projects/last30days-skill-zhcn
git status
git branch --show-current
```
Expected: `main`, clean working tree (spec commit `5e21b42` already landed).

- [ ] **Step 2: Create branch**

```bash
git checkout -b feat/bilibili-adapter
```

- [ ] **Step 3: Confirm branch**

```bash
git branch --show-current
```
Expected: `feat/bilibili-adapter`

---

## Phase 1: WBI Signing Module (→ Commit 1)

### Task 1: Create nav fixture

**Files:**
- Create: `fixtures/bilibili/nav_response.json`

- [ ] **Step 1: Create fixture directory**

```bash
mkdir -p fixtures/bilibili
```

- [ ] **Step 2: Write `fixtures/bilibili/nav_response.json`**

This is a minimal-but-real-shape sanitized `/x/web-interface/nav` response (anonymous, no login). The `img_url`/`sub_url` filenames give us deterministic `img_key`/`sub_key`.

```json
{
  "code": 0,
  "message": "0",
  "ttl": 1,
  "data": {
    "isLogin": false,
    "wbi_img": {
      "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
      "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"
    }
  }
}
```

- [ ] **Step 3: Verify the fixture parses**

```bash
python -c "import json; print(json.load(open('fixtures/bilibili/nav_response.json'))['data']['wbi_img']['img_url'])"
```
Expected: prints the img_url.

### Task 2: Skeleton `bilibili_wbi.py` with MIXIN_KEY_ENC_TAB constant

**Files:**
- Create: `skills/last30days/scripts/lib/bilibili_wbi.py`
- Test: `tests/lib/test_bilibili_wbi.py`

- [ ] **Step 1: Write failing test for constant existence**

Create `tests/lib/test_bilibili_wbi.py`:
```python
"""Tests for skills/last30days/scripts/lib/bilibili_wbi.py."""

from skills.last30days.scripts.lib import bilibili_wbi


def test_mixin_key_enc_tab_length_is_64():
    assert len(bilibili_wbi.MIXIN_KEY_ENC_TAB) == 64


def test_mixin_key_enc_tab_values_unique():
    assert len(set(bilibili_wbi.MIXIN_KEY_ENC_TAB)) == 64


def test_mixin_key_enc_tab_values_in_range():
    assert all(0 <= v < 64 for v in bilibili_wbi.MIXIN_KEY_ENC_TAB)
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
pytest tests/lib/test_bilibili_wbi.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'skills.last30days.scripts.lib.bilibili_wbi'`.

- [ ] **Step 3: Create `skills/last30days/scripts/lib/bilibili_wbi.py`**

```python
"""WBI signature helpers for Bilibili web APIs.

Pure-function module — no HTTP, no global state. The 64-byte permutation
table (MIXIN_KEY_ENC_TAB) is the documented Bilibili-public constant from
SocialSisterYi/bilibili-API-collect (docs/misc/sign/wbi.md). It maps
positions in (img_key + sub_key) onto positions in the 32-char mixin_key.
"""

from __future__ import annotations

import hashlib
import time
import urllib.parse
from typing import Any

MIXIN_KEY_ENC_TAB: list[int] = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]
```

- [ ] **Step 4: Run tests, expect pass**

```bash
pytest tests/lib/test_bilibili_wbi.py -v
```
Expected: 3 passed.

### Task 3: `get_wbi_keys()` — extract img_key/sub_key from nav response

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili_wbi.py`
- Modify: `tests/lib/test_bilibili_wbi.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/lib/test_bilibili_wbi.py`:
```python
import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "bilibili"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_get_wbi_keys_extracts_from_nav_response():
    nav = _load_fixture("nav_response.json")
    img_key, sub_key = bilibili_wbi.get_wbi_keys(nav)
    assert img_key == "7cd084941338484aae1ad9425b84077c"
    assert sub_key == "4932caff0ff746eab6f01bf08b70ac45"


def test_get_wbi_keys_raises_on_missing_field():
    with pytest.raises(ValueError):
        bilibili_wbi.get_wbi_keys({"code": 0, "data": {}})


def test_get_wbi_keys_raises_on_malformed_url():
    bad = {"data": {"wbi_img": {"img_url": "https://example.com/", "sub_url": "https://example.com/"}}}
    with pytest.raises(ValueError):
        bilibili_wbi.get_wbi_keys(bad)
```

Note on FIXTURES path: it walks up from `tests/lib/test_bilibili_wbi.py` to repo root (3 levels), then into `fixtures/bilibili`. Verify the path resolves before the test runs:
```bash
python -c "import pathlib; p = pathlib.Path('tests/lib/test_bilibili_wbi.py').parent.parent.parent / 'fixtures' / 'bilibili' / 'nav_response.json'; print(p.exists(), p.resolve())"
```
Expected: `True <absolute path>`.

- [ ] **Step 2: Run tests, expect fail**

```bash
pytest tests/lib/test_bilibili_wbi.py -v
```
Expected: 3 FAIL with `AttributeError: module ... has no attribute 'get_wbi_keys'`.

- [ ] **Step 3: Implement `get_wbi_keys` in `bilibili_wbi.py`**

Append to `bilibili_wbi.py`:
```python
def get_wbi_keys(nav_json: dict[str, Any]) -> tuple[str, str]:
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
```

- [ ] **Step 4: Run tests, expect pass**

```bash
pytest tests/lib/test_bilibili_wbi.py -v
```
Expected: 6 passed.

### Task 4: `mix_key()` — apply permutation table

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili_wbi.py`
- Modify: `tests/lib/test_bilibili_wbi.py`

- [ ] **Step 1: Write failing test**

Append to `tests/lib/test_bilibili_wbi.py`:
```python
def test_mix_key_returns_32_chars():
    img_key = "7cd084941338484aae1ad9425b84077c"
    sub_key = "4932caff0ff746eab6f01bf08b70ac45"
    mixin = bilibili_wbi.mix_key(img_key, sub_key)
    assert len(mixin) == 32


def test_mix_key_uses_permutation_table():
    """mix_key picks chars from (img+sub) at positions given by MIXIN_KEY_ENC_TAB."""
    img_key = "7cd084941338484aae1ad9425b84077c"
    sub_key = "4932caff0ff746eab6f01bf08b70ac45"
    combined = img_key + sub_key
    mixin = bilibili_wbi.mix_key(img_key, sub_key)
    for i, src_pos in enumerate(bilibili_wbi.MIXIN_KEY_ENC_TAB[:32]):
        assert mixin[i] == combined[src_pos], f"position {i} should map from {src_pos}"
```

- [ ] **Step 2: Run tests, expect fail**

```bash
pytest tests/lib/test_bilibili_wbi.py -v
```
Expected: 2 new FAIL with `AttributeError`.

- [ ] **Step 3: Implement `mix_key`**

Append to `bilibili_wbi.py`:
```python
def mix_key(img_key: str, sub_key: str) -> str:
    """Permute (img_key + sub_key) by MIXIN_KEY_ENC_TAB, truncate to 32 chars."""
    combined = img_key + sub_key
    return "".join(combined[i] for i in MIXIN_KEY_ENC_TAB)[:32]
```

- [ ] **Step 4: Run tests, expect pass**

```bash
pytest tests/lib/test_bilibili_wbi.py -v
```
Expected: 8 passed.

### Task 5: `sign_params()` — add wts + w_rid

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili_wbi.py`
- Modify: `tests/lib/test_bilibili_wbi.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/lib/test_bilibili_wbi.py`:
```python
def test_sign_params_adds_wts_and_w_rid():
    signed = bilibili_wbi.sign_params(
        {"foo": "bar"}, mixin_key="a" * 32, ts=1702204169
    )
    assert signed["wts"] == 1702204169
    assert "w_rid" in signed
    assert len(signed["w_rid"]) == 32  # MD5 hex


def test_sign_params_does_not_mutate_input():
    original = {"foo": "bar"}
    bilibili_wbi.sign_params(original, mixin_key="a" * 32, ts=1)
    assert original == {"foo": "bar"}
    assert "wts" not in original


def test_sign_params_default_ts_is_now(monkeypatch):
    monkeypatch.setattr(bilibili_wbi.time, "time", lambda: 1700000000.5)
    signed = bilibili_wbi.sign_params({"x": "1"}, mixin_key="a" * 32)
    assert signed["wts"] == 1700000000


def test_sign_params_w_rid_is_deterministic():
    """Same inputs → same output."""
    a = bilibili_wbi.sign_params({"k": "v"}, mixin_key="m" * 32, ts=42)
    b = bilibili_wbi.sign_params({"k": "v"}, mixin_key="m" * 32, ts=42)
    assert a["w_rid"] == b["w_rid"]


def test_sign_params_w_rid_matches_md5_of_sorted_query_plus_key():
    """Verifies the actual algorithm: MD5(sorted-urlencoded-params + mixin_key)."""
    import hashlib as _hl
    import urllib.parse as _up

    params = {"foo": "114", "bar": "514", "baz": "1919810"}
    mixin = "ea1db124af3c7062474693fa704f4ff8"
    ts = 1702204169

    expected_query = _up.urlencode(sorted({**params, "wts": ts}.items()))
    expected_w_rid = _hl.md5((expected_query + mixin).encode("utf-8")).hexdigest()

    signed = bilibili_wbi.sign_params(params, mixin_key=mixin, ts=ts)
    assert signed["w_rid"] == expected_w_rid
```

- [ ] **Step 2: Run tests, expect fail**

```bash
pytest tests/lib/test_bilibili_wbi.py -v
```
Expected: 5 new FAIL with `AttributeError`.

- [ ] **Step 3: Implement `sign_params`**

Append to `bilibili_wbi.py`:
```python
def sign_params(
    params: dict[str, Any],
    mixin_key: str,
    *,
    ts: int | None = None,
) -> dict[str, Any]:
    """Return a new params dict with `wts` and `w_rid` added.

    Algorithm (per SocialSisterYi/bilibili-API-collect wbi.md):
      1. wts = int(time.time()) unless `ts` is injected (test seam).
      2. Sort the union of params and {wts}, URL-encode each value.
      3. Join as k1=v1&k2=v2&...
      4. Append mixin_key, MD5, hex-digest → w_rid.

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
```

- [ ] **Step 4: Run tests, expect pass**

```bash
pytest tests/lib/test_bilibili_wbi.py -v
```
Expected: 13 passed.

### Task 6: Commit Phase 1

- [ ] **Step 1: Review staged diff**

```bash
git add skills/last30days/scripts/lib/bilibili_wbi.py tests/lib/test_bilibili_wbi.py fixtures/bilibili/nav_response.json
git diff --cached --stat
```
Expected: 3 files added, ~150 lines.

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(bilibili): add WBI signing module

Adds skills/last30days/scripts/lib/bilibili_wbi.py — a pure-function
helper for Bilibili's WBI (web bot interception) signature scheme.
Implements get_wbi_keys (extract img_key/sub_key from /x/web-interface/nav),
mix_key (apply the 64-byte permutation table), and sign_params (add wts
and w_rid to a request param dict). No HTTP, no state. Fully unit-tested
against the algorithm documented in SocialSisterYi/bilibili-API-collect.

13 tests, fixture-based, no live network.
EOF
)"
```

- [ ] **Step 3: Verify**

```bash
git log -1 --stat
```
Expected: 1 commit, 3 files.

---

## Phase 2: Search Adapter (→ Commit 2)

### Task 7: Search response and v_voucher fixtures

**Files:**
- Create: `fixtures/bilibili/search_video_response.json`
- Create: `fixtures/bilibili/v_voucher_response.json`

- [ ] **Step 1: Write `fixtures/bilibili/search_video_response.json`**

Minimal sanitized response shape — 3 video items spanning a date range so we can test date filtering. Values mirror the real B站 API.

```json
{
  "code": 0,
  "message": "0",
  "ttl": 1,
  "data": {
    "seid": "0",
    "page": 1,
    "pagesize": 20,
    "numResults": 3,
    "numPages": 1,
    "result": [
      {
        "type": "video",
        "id": 100001,
        "author": "测试UP主A",
        "mid": 12345,
        "bvid": "BV1AA1xxxxxx",
        "aid": 100001,
        "title": "<em class=\"keyword\">长沙麻将</em>新手入门教程",
        "description": "长沙麻将基础规则讲解，适合新手快速上手。",
        "pic": "//i0.hdslb.com/bfs/archive/aaa.jpg",
        "play": 124000,
        "video_review": 1100,
        "favorites": 3400,
        "review": 220,
        "like": 8200,
        "duration": "4:05",
        "pubdate": 1748390400,
        "senddate": 1748390400
      },
      {
        "type": "video",
        "id": 100002,
        "author": "测试UP主B",
        "mid": 67890,
        "bvid": "BV1BB2yyyyyy",
        "aid": 100002,
        "title": "长沙麻将高手对局解说",
        "description": "复盘真实牌局，讲解胡牌与防守思路。",
        "pic": "//i0.hdslb.com/bfs/archive/bbb.jpg",
        "play": 56000,
        "video_review": 480,
        "favorites": 1100,
        "review": 95,
        "like": 3200,
        "duration": "12:30",
        "pubdate": 1746576000,
        "senddate": 1746576000
      },
      {
        "type": "video",
        "id": 100003,
        "author": "测试UP主C",
        "mid": 24680,
        "bvid": "BV1CC3zzzzzz",
        "aid": 100003,
        "title": "麻将历史档案 2020 年",
        "description": "怀旧向，发布于早期。",
        "pic": "//i0.hdslb.com/bfs/archive/ccc.jpg",
        "play": 9000,
        "video_review": 50,
        "favorites": 110,
        "review": 8,
        "like": 220,
        "duration": "8:15",
        "pubdate": 1577836800,
        "senddate": 1577836800
      }
    ]
  }
}
```

Note: `pubdate` 1748390400 ≈ 2025-05-28, 1746576000 ≈ 2025-05-07, 1577836800 = 2020-01-01.

- [ ] **Step 2: Write `fixtures/bilibili/v_voucher_response.json`**

```json
{
  "code": -352,
  "message": "风控校验失败",
  "ttl": 1,
  "data": {
    "v_voucher": "voucher_abcdef123456"
  }
}
```

- [ ] **Step 3: Verify both parse**

```bash
python -c "import json; [json.load(open(p)) for p in ['fixtures/bilibili/search_video_response.json', 'fixtures/bilibili/v_voucher_response.json']]; print('ok')"
```
Expected: `ok`.

### Task 8: Skeleton `bilibili.py` with module constants

**Files:**
- Create: `skills/last30days/scripts/lib/bilibili.py`
- Test: `tests/lib/test_bilibili.py`

- [ ] **Step 1: Write failing test for module constants**

Create `tests/lib/test_bilibili.py`:
```python
"""Tests for skills/last30days/scripts/lib/bilibili.py."""

import json
import pathlib

import pytest

from skills.last30days.scripts.lib import bilibili

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "bilibili"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_constants_exist():
    assert bilibili.NAV_URL == "https://api.bilibili.com/x/web-interface/nav"
    assert bilibili.SEARCH_URL == "https://api.bilibili.com/x/web-interface/wbi/search/type"
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: ImportError.

- [ ] **Step 3: Create `skills/last30days/scripts/lib/bilibili.py`**

```python
"""Bilibili search adapter for last30days.

Uses Bilibili's public web search API:
  GET https://api.bilibili.com/x/web-interface/wbi/search/type

WBI-signed via bilibili_wbi.sign_params. buvid3 cookie is auto-bootstrapped
on first use (no user login required). Module-level caches keep the
bootstrap to one-shot per Python process.

Modeled after skills/last30days/scripts/lib/xiaohongshu_api.py.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from typing import Any

from . import bilibili_wbi, http

NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
SEARCH_URL = "https://api.bilibili.com/x/web-interface/wbi/search/type"
BOOTSTRAP_URL = "https://www.bilibili.com/"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
```

- [ ] **Step 4: Run test, expect pass**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 1 passed.

### Task 9: `_to_int()` — Chinese-numeral parsing

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili.py`
- Modify: `tests/lib/test_bilibili.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/lib/test_bilibili.py`:
```python
def test_to_int_handles_plain_int():
    assert bilibili._to_int(124000) == 124000


def test_to_int_handles_plain_str():
    assert bilibili._to_int("124000") == 124000


def test_to_int_handles_wan_suffix():
    assert bilibili._to_int("1.2万") == 12000
    assert bilibili._to_int("12万") == 120000


def test_to_int_handles_yi_suffix():
    assert bilibili._to_int("3亿") == 300000000


def test_to_int_handles_comma_separated():
    assert bilibili._to_int("1,234") == 1234


def test_to_int_handles_none():
    assert bilibili._to_int(None) == 0


def test_to_int_handles_garbage():
    assert bilibili._to_int("not a number") == 0
    assert bilibili._to_int("") == 0
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 7 new FAIL.

- [ ] **Step 3: Implement `_to_int`**

Append to `bilibili.py`:
```python
def _to_int(value: Any) -> int:
    """Convert engagement count to int. Supports plain ints/strings and
    Chinese suffixes 万 (×10⁴) and 亿 (×10⁸).

    Private to this module for the first PR. A future PR may extract this
    to lib/normalize.py once Weibo/Zhihu adapters share the pattern.
    """
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return 0

    try:
        if text.endswith("万"):
            return int(float(text[:-1]) * 10_000)
        if text.endswith("亿"):
            return int(float(text[:-1]) * 100_000_000)
        return int(float(text))
    except (TypeError, ValueError):
        return 0
```

- [ ] **Step 4: Run, expect pass**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 8 passed.

### Task 10: `_relevance_from_interactions()` — engagement scoring

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili.py`
- Modify: `tests/lib/test_bilibili.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/lib/test_bilibili.py`:
```python
def test_relevance_clamped_min_to_0_05():
    # zero engagement → floor
    assert bilibili._relevance_from_interactions(0, 0, 0, 0, 0) == 0.05


def test_relevance_clamped_max_to_1_0():
    # huge engagement → ceiling
    assert bilibili._relevance_from_interactions(10**9, 10**9, 10**9, 10**9, 10**9) == 1.0


def test_relevance_coin_weighted_higher_than_favorite():
    """1 coin > 1 favorite at same other-metric levels."""
    base = bilibili._relevance_from_interactions(100, 100, 100, 0, 0)
    with_fav = bilibili._relevance_from_interactions(100, 100, 100, 100, 0)
    with_coin = bilibili._relevance_from_interactions(100, 100, 100, 0, 100)
    assert with_coin > with_fav > base


def test_relevance_in_normal_range():
    """A moderately popular video should land around 0.5."""
    score = bilibili._relevance_from_interactions(
        play=100_000, like=3_000, danmaku=500, favorite=1_500, coin=2_000
    )
    assert 0.3 <= score <= 0.7
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 4 new FAIL.

- [ ] **Step 3: Implement `_relevance_from_interactions`**

Append to `bilibili.py`:
```python
def _relevance_from_interactions(
    play: int,
    like: int,
    danmaku: int,
    favorite: int,
    coin: int,
) -> float:
    """Heuristic 0.05–1.0 relevance from B站 engagement signals.

    Weights (descending): coin > favorite > like > danmaku > play.
    Rationale: coins cost users a finite weekly budget — strongest signal.
    Favorites imply retention intent. Likes are light affirmation. Danmaku
    is B站-specific participation. Plays are passive baseline.

    Denominator 50_000 calibrated so a moderately popular video scores ~0.5
    and a viral one approaches 1.0.
    """
    weighted = play * 1.0 + like * 2.0 + danmaku * 1.5 + favorite * 2.5 + coin * 3.0
    return round(min(1.0, max(0.05, weighted / 50_000.0)), 3)
```

- [ ] **Step 4: Run, expect pass**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 12 passed.

### Task 11: `_parse_duration()` and `_pubdate_to_iso()` helpers

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili.py`
- Modify: `tests/lib/test_bilibili.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/lib/test_bilibili.py`:
```python
def test_parse_duration_mmss():
    assert bilibili._parse_duration("4:05") == 245


def test_parse_duration_hhmmss():
    assert bilibili._parse_duration("1:02:03") == 3723


def test_parse_duration_garbage():
    assert bilibili._parse_duration("") == 0
    assert bilibili._parse_duration(None) == 0
    assert bilibili._parse_duration("abc") == 0


def test_pubdate_to_iso_valid_epoch():
    # 1748390400 = 2025-05-28 00:00:00 UTC
    assert bilibili._pubdate_to_iso(1748390400) == "2025-05-28"


def test_pubdate_to_iso_zero_returns_none():
    assert bilibili._pubdate_to_iso(0) is None


def test_pubdate_to_iso_invalid_returns_none():
    assert bilibili._pubdate_to_iso("garbage") is None
    assert bilibili._pubdate_to_iso(None) is None
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 6 new FAIL.

- [ ] **Step 3: Implement helpers**

Append to `bilibili.py`:
```python
def _parse_duration(value: Any) -> int:
    """Parse '4:05' or '1:02:03' style duration to seconds. 0 on failure."""
    if not isinstance(value, str) or not value:
        return 0
    parts = value.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0


def _pubdate_to_iso(value: Any) -> str | None:
    """Convert a Unix epoch (int seconds) to YYYY-MM-DD UTC. None on failure."""
    try:
        iv = int(value)
    except (TypeError, ValueError):
        return None
    if iv <= 0:
        return None
    try:
        return datetime.fromtimestamp(iv, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, ValueError):
        return None
```

- [ ] **Step 4: Run, expect pass**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 18 passed.

### Task 12: `_strip_em_tags()` — remove search highlight tags

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili.py`
- Modify: `tests/lib/test_bilibili.py`

The search API embeds matched keywords in `<em class="keyword">...</em>` HTML in `title`. Strip for clean display.

- [ ] **Step 1: Write failing tests**

Append to `tests/lib/test_bilibili.py`:
```python
def test_strip_em_tags_removes_em_wrappers():
    s = '<em class="keyword">长沙</em>麻将入门'
    assert bilibili._strip_em_tags(s) == "长沙麻将入门"


def test_strip_em_tags_handles_multiple():
    s = '<em class="keyword">A</em>B<em class="keyword">C</em>D'
    assert bilibili._strip_em_tags(s) == "ABCD"


def test_strip_em_tags_passthrough_when_clean():
    assert bilibili._strip_em_tags("plain title") == "plain title"


def test_strip_em_tags_handles_empty():
    assert bilibili._strip_em_tags("") == ""
    assert bilibili._strip_em_tags(None) == ""
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 4 new FAIL.

- [ ] **Step 3: Implement `_strip_em_tags`**

Append to `bilibili.py`, after the constants block import-area (top-level, near `_USER_AGENT`):
```python
import re as _re

_EM_TAG_PATTERN = _re.compile(r'</?em[^>]*>')


def _strip_em_tags(text: Any) -> str:
    """Remove <em>...</em> search-highlight tags from a string."""
    if not isinstance(text, str):
        return ""
    return _EM_TAG_PATTERN.sub("", text)
```

- [ ] **Step 4: Run, expect pass**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 22 passed.

### Task 13: `_ensure_session()` — cookie bootstrap with caching

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili.py`
- Modify: `tests/lib/test_bilibili.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/lib/test_bilibili.py`:
```python
def test_ensure_session_calls_bootstrap_once(monkeypatch):
    """Two calls to _ensure_session in one process → bootstrap fires once."""
    bilibili._reset_session_cache()  # test-only helper

    calls = {"buvid": 0, "nav": 0}

    def fake_fetch_buvid3():
        calls["buvid"] += 1
        return "FAKE_BUVID3_VALUE"

    def fake_http_get(url, headers=None, **kwargs):
        calls["nav"] += 1
        return _load("nav_response.json")

    monkeypatch.setattr(bilibili, "_fetch_buvid3", fake_fetch_buvid3)
    monkeypatch.setattr(bilibili.http, "get", fake_http_get)

    a_mixin, a_cookies = bilibili._ensure_session()
    b_mixin, b_cookies = bilibili._ensure_session()

    assert a_mixin == b_mixin
    assert a_cookies == b_cookies
    assert calls["buvid"] == 1
    assert calls["nav"] == 1
    assert a_cookies["buvid3"] == "FAKE_BUVID3_VALUE"
    assert len(a_mixin) == 32


def test_ensure_session_raises_on_bootstrap_failure(monkeypatch):
    bilibili._reset_session_cache()

    def fake_fetch_buvid3():
        raise http.HTTPError("bootstrap GET failed")

    monkeypatch.setattr(bilibili, "_fetch_buvid3", fake_fetch_buvid3)

    with pytest.raises(http.HTTPError) as exc:
        bilibili._ensure_session()
    assert "cookie bootstrap failed" in str(exc.value)


def test_ensure_session_raises_on_bad_nav_response(monkeypatch):
    bilibili._reset_session_cache()
    monkeypatch.setattr(bilibili, "_fetch_buvid3", lambda: "BUVID")
    monkeypatch.setattr(bilibili.http, "get", lambda url, **kw: {"code": -1, "data": {}})

    with pytest.raises(http.HTTPError):
        bilibili._ensure_session()
```

Also import `http` at the top of `test_bilibili.py` if not already:
```python
from skills.last30days.scripts.lib import http
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 3 new FAIL.

- [ ] **Step 3: Implement `_ensure_session` and helpers**

Append to `bilibili.py`:
```python
# Module-level cache: bootstrap only once per Python process.
_mixin_key_cache: str | None = None
_cookie_jar_cache: dict[str, str] | None = None


def _reset_session_cache() -> None:
    """Clear cached bootstrap state. Test-only helper."""
    global _mixin_key_cache, _cookie_jar_cache
    _mixin_key_cache = None
    _cookie_jar_cache = None


def _fetch_buvid3() -> str:
    """GET https://www.bilibili.com/ and extract buvid3 from Set-Cookie.

    Uses urllib directly because http.py does not expose response headers.
    Returns the buvid3 cookie value, or raises http.HTTPError on failure.
    """
    req = urllib.request.Request(
        BOOTSTRAP_URL,
        headers={"User-Agent": _USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            set_cookies = resp.headers.get_all("Set-Cookie") or []
    except (urllib.error.URLError, OSError) as exc:
        raise http.HTTPError(f"Bilibili bootstrap GET failed: {exc}") from exc

    for raw in set_cookies:
        # raw is like 'buvid3=abc...; Path=/; Domain=.bilibili.com; ...'
        first = raw.split(";", 1)[0].strip()
        if "=" in first:
            name, value = first.split("=", 1)
            if name.strip() == "buvid3" and value.strip():
                return value.strip()
    raise http.HTTPError("Bilibili bootstrap: buvid3 not in Set-Cookie")


def _ensure_session() -> tuple[str, dict[str, str]]:
    """Return (mixin_key, cookie_jar). Bootstrap once, then cache."""
    global _mixin_key_cache, _cookie_jar_cache
    if _mixin_key_cache and _cookie_jar_cache:
        return _mixin_key_cache, _cookie_jar_cache

    try:
        buvid3 = _fetch_buvid3()
        cookies = {"buvid3": buvid3}
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        nav_json = http.get(
            NAV_URL,
            headers={
                "User-Agent": _USER_AGENT,
                "Referer": "https://www.bilibili.com/",
                "Cookie": cookie_header,
            },
            timeout=10,
            retries=2,
        )
        if not isinstance(nav_json, dict) or nav_json.get("code") != 0:
            raise http.HTTPError(f"Bilibili nav returned non-zero: {nav_json}")
        img_key, sub_key = bilibili_wbi.get_wbi_keys(nav_json)
        mixin = bilibili_wbi.mix_key(img_key, sub_key)
    except http.HTTPError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        raise http.HTTPError(f"Bilibili: cookie bootstrap failed: {exc}") from exc

    _mixin_key_cache = mixin
    _cookie_jar_cache = cookies
    return mixin, cookies
```

- [ ] **Step 4: Run, expect pass**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 25 passed.

### Task 14: `search_bilibili()` — main entry point

**Files:**
- Modify: `skills/last30days/scripts/lib/bilibili.py`
- Modify: `tests/lib/test_bilibili.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/lib/test_bilibili.py`:
```python
@pytest.fixture(autouse=True)
def _reset_bilibili_session():
    """Reset module cache between tests so monkeypatches don't leak."""
    bilibili._reset_session_cache()
    yield
    bilibili._reset_session_cache()


def _patch_session(monkeypatch):
    """Skip real bootstrap; install a deterministic mixin_key + cookies."""
    monkeypatch.setattr(bilibili, "_ensure_session", lambda: ("a" * 32, {"buvid3": "X"}))


def test_search_bilibili_normalizes_fixture_response(monkeypatch):
    _patch_session(monkeypatch)
    monkeypatch.setattr(bilibili.http, "get", lambda url, **kw: _load("search_video_response.json"))

    items = bilibili.search_bilibili(
        topic="长沙麻将",
        from_date="2025-01-01",
        to_date="2025-12-31",
        depth="default",
    )
    # Date filter drops the 2020 item.
    assert len(items) == 2

    first = items[0]
    assert first["id"] == "BILI1"
    assert first["url"] == "https://www.bilibili.com/video/BV1AA1xxxxxx"
    assert first["source_domain"] == "bilibili.com"
    assert first["date"] == "2025-05-28"
    assert first["date_confidence"] == "high"
    assert "长沙麻将" in first["title"]  # em-tag stripped
    assert first["engagement"]["play"] == 124000
    assert first["engagement"]["coin"] >= 0  # field present even if fixture omits
    assert first["extra"]["bvid"] == "BV1AA1xxxxxx"
    assert first["extra"]["author"] == "测试UP主A"
    assert 0.05 <= first["relevance"] <= 1.0


def test_search_bilibili_filters_by_date_range(monkeypatch):
    _patch_session(monkeypatch)
    monkeypatch.setattr(bilibili.http, "get", lambda url, **kw: _load("search_video_response.json"))

    items = bilibili.search_bilibili(
        topic="麻将",
        from_date="2025-05-15",
        to_date="2025-06-01",
        depth="default",
    )
    # Only the 2025-05-28 video falls in this window.
    assert len(items) == 1
    assert items[0]["date"] == "2025-05-28"


def test_search_bilibili_respects_depth_caps(monkeypatch):
    _patch_session(monkeypatch)

    captured = {}

    def fake_get(url, **kw):
        captured["params"] = kw.get("params", {})
        return _load("search_video_response.json")

    monkeypatch.setattr(bilibili.http, "get", fake_get)

    bilibili.search_bilibili("x", "2020-01-01", "2030-01-01", depth="quick")
    assert captured["params"]["page_size"] == 10

    bilibili.search_bilibili("x", "2020-01-01", "2030-01-01", depth="default")
    assert captured["params"]["page_size"] == 20

    bilibili.search_bilibili("x", "2020-01-01", "2030-01-01", depth="deep")
    assert captured["params"]["page_size"] == 30


def test_search_bilibili_raises_on_v_voucher(monkeypatch):
    _patch_session(monkeypatch)
    monkeypatch.setattr(bilibili.http, "get", lambda url, **kw: _load("v_voucher_response.json"))

    with pytest.raises(http.HTTPError) as exc:
        bilibili.search_bilibili("x", "2020-01-01", "2030-01-01")
    msg = str(exc.value)
    assert "WBI" in msg or "v_voucher" in msg or "-352" in msg


def test_search_bilibili_handles_empty_result_list(monkeypatch):
    _patch_session(monkeypatch)
    monkeypatch.setattr(
        bilibili.http, "get",
        lambda url, **kw: {"code": 0, "data": {"result": []}},
    )
    items = bilibili.search_bilibili("nothing matches", "2020-01-01", "2030-01-01")
    assert items == []


def test_search_bilibili_signs_request_params(monkeypatch):
    _patch_session(monkeypatch)

    captured = {}

    def fake_get(url, **kw):
        captured["params"] = kw.get("params", {})
        return _load("search_video_response.json")

    monkeypatch.setattr(bilibili.http, "get", fake_get)
    bilibili.search_bilibili("test", "2020-01-01", "2030-01-01")

    assert "wts" in captured["params"]
    assert "w_rid" in captured["params"]
    assert captured["params"]["search_type"] == "video"
    assert captured["params"]["keyword"] == "test"
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 6 new FAIL.

- [ ] **Step 3: Implement `search_bilibili`**

Append to `bilibili.py`:
```python
_DEPTH_PAGE_SIZE = {"quick": 10, "default": 20, "deep": 30}


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _build_video_url(bvid: str) -> str:
    return f"https://www.bilibili.com/video/{bvid}"


def search_bilibili(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> list[dict[str, Any]]:
    """Search Bilibili videos for `topic`, return normalized web-items.

    Args:
        topic: Search keyword (Chinese or English).
        from_date: Inclusive lower bound, "YYYY-MM-DD".
        to_date: Inclusive upper bound, "YYYY-MM-DD".
        depth: "quick" | "default" | "deep" → page_size 10/20/30.

    Returns:
        List of normalized item dicts (see bilibili.py docstring schema).
        Empty list if no results match the date window.

    Raises:
        http.HTTPError if bootstrap, signing, or search fails. The pipeline
        catches and drops the source for the current run.
    """
    mixin_key, cookies = _ensure_session()
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())

    params = {
        "search_type": "video",
        "keyword": topic,
        "order": "totalrank",
        "page": 1,
        "page_size": _DEPTH_PAGE_SIZE.get(depth, 20),
    }
    signed = bilibili_wbi.sign_params(params, mixin_key)

    resp = http.get(
        SEARCH_URL,
        params=signed,
        headers={
            "User-Agent": _USER_AGENT,
            "Referer": "https://www.bilibili.com/",
            "Cookie": cookie_header,
        },
        timeout=15,
        retries=1,
    )

    if not isinstance(resp, dict):
        raise http.HTTPError(f"Bilibili search: unexpected response shape: {type(resp).__name__}")

    code = resp.get("code", -1)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    if code != 0:
        # -352 (and several other codes) come with a v_voucher; treat as WBI signature failure.
        if "v_voucher" in data:
            raise http.HTTPError(
                f"Bilibili search: WBI signature may have rotated (code={code}, v_voucher present). "
                "Re-verify MIXIN_KEY_ENC_TAB and signing algorithm."
            )
        raise http.HTTPError(f"Bilibili search: code={code} message={resp.get('message')!r}")

    raw_items = data.get("result", []) if isinstance(data.get("result"), list) else []
    from_d = _parse_date(from_date)
    to_d = _parse_date(to_date)

    out: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            continue
        item = _normalize_video(raw, index=len(out) + 1)
        if item is None:
            continue
        if item["date"]:
            d = _parse_date(item["date"])
            if d < from_d or d > to_d:
                continue
        out.append(item)
    return out


def _normalize_video(raw: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    """Convert a raw search result item into the web-item schema."""
    bvid = str(raw.get("bvid") or "").strip()
    if not bvid:
        return None

    title = _strip_em_tags(raw.get("title")).strip()
    description = str(raw.get("description") or "").strip()
    pubdate = raw.get("pubdate") or raw.get("senddate")
    iso = _pubdate_to_iso(pubdate)

    play = _to_int(raw.get("play"))
    like = _to_int(raw.get("like"))
    danmaku = _to_int(raw.get("video_review"))  # B站 API names danmaku as video_review
    favorite = _to_int(raw.get("favorites"))
    review = _to_int(raw.get("review"))  # comment count
    # `coin` is not directly returned by /search/type; default to 0. A future
    # PR (hot-comment enrichment) may fetch per-video stats including coins.
    coin = _to_int(raw.get("coin"))
    share = _to_int(raw.get("share"))

    relevance = _relevance_from_interactions(play, like, danmaku, favorite, coin)

    why = (
        f"Bilibili engagement: play={play}, like={like}, "
        f"danmaku={danmaku}, favorite={favorite}, coin={coin}"
    )

    return {
        "id": f"BILI{index}",
        "title": title[:200] if title else f"Bilibili video {bvid}",
        "url": _build_video_url(bvid),
        "source_domain": "bilibili.com",
        "snippet": description[:500],
        "date": iso,
        "date_confidence": "high" if iso else "low",
        "relevance": relevance,
        "why_relevant": why,
        "engagement": {
            "play": play,
            "like": like,
            "danmaku": danmaku,
            "favorite": favorite,
            "coin": coin,
            "share": share,
            "review": review,
        },
        "extra": {
            "author": str(raw.get("author") or "").strip(),
            "author_mid": _to_int(raw.get("mid")),
            "bvid": bvid,
            "duration": _parse_duration(raw.get("duration")),
        },
    }
```

- [ ] **Step 4: Run, expect pass**

```bash
pytest tests/lib/test_bilibili.py -v
```
Expected: 31 passed.

### Task 15: Commit Phase 2

- [ ] **Step 1: Stage and review**

```bash
git add skills/last30days/scripts/lib/bilibili.py \
        tests/lib/test_bilibili.py \
        fixtures/bilibili/search_video_response.json \
        fixtures/bilibili/v_voucher_response.json
git diff --cached --stat
```
Expected: 4 files added (~600 lines total).

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(bilibili): add search adapter with cookie bootstrap

Adds skills/last30days/scripts/lib/bilibili.py, the public-search
adapter modeled after xiaohongshu_api.py. search_bilibili(topic,
from_date, to_date, depth) hits /x/web-interface/wbi/search/type
and returns normalized web-items.

buvid3 cookie is auto-fetched from www.bilibili.com on first use
(zero user configuration). WBI signing is delegated to bilibili_wbi.
Module-level cache keeps bootstrap to one round-trip per Python
process. v_voucher responses are translated into HTTPError so the
pipeline can drop the source cleanly.

18 unit tests, all fixture-based.
EOF
)"
```

- [ ] **Step 3: Verify**

```bash
git log -1 --stat
```

---

## Phase 3: Registration (→ Commit 3)

Each registration touches a different file. The order here is by independence — files that don't import each other go first.

### Task 16: `env.py` — `is_bilibili_available`

**Files:**
- Modify: `skills/last30days/scripts/lib/env.py` (append at end)

- [ ] **Step 1: Inspect existing patterns**

```bash
grep -n "is_xiaohongshu_available\|def get_xiaohongshu" skills/last30days/scripts/lib/env.py
```

- [ ] **Step 2: Add new function**

Append to `env.py`:
```python
def is_bilibili_available(config: dict[str, Any]) -> bool:
    """Bilibili is always available unless explicitly disabled.

    The adapter auto-bootstraps a buvid3 cookie and uses public WBI-signed
    search — no API key, no login. Honors LAST30DAYS_DISABLE_BILIBILI=1 as
    a kill switch for operators who want to skip the source.
    """
    import os

    if os.environ.get("LAST30DAYS_DISABLE_BILIBILI") == "1":
        return False
    return True
```

- [ ] **Step 3: Sanity-check import**

```bash
python -c "from skills.last30days.scripts.lib import env; print(env.is_bilibili_available({}))"
```
Expected: `True`.

- [ ] **Step 4: With kill switch**

```bash
LAST30DAYS_DISABLE_BILIBILI=1 python -c "from skills.last30days.scripts.lib import env; print(env.is_bilibili_available({}))"
```
Expected: `False`. (On PowerShell: `$env:LAST30DAYS_DISABLE_BILIBILI="1"; python -c "..."`.)

### Task 17: `signals.py` — source quality weight

**Files:**
- Modify: `skills/last30days/scripts/lib/signals.py:11-22`

- [ ] **Step 1: Locate the SOURCE_QUALITY dict and add an entry**

Open `signals.py`, find:
```python
SOURCE_QUALITY = {
    "xiaohongshu": 0.7,
    "hackernews": 0.8,
    ...
}
```

Add `"bilibili": 0.7,` as a sibling of xiaohongshu (alphabetical order is not enforced by the project — match the existing arrangement and place next to xiaohongshu).

- [ ] **Step 2: Verify**

```bash
python -c "from skills.last30days.scripts.lib import signals; print(signals.source_quality('bilibili'))"
```
Expected: `0.7`.

### Task 18: `normalize.py` — register normalizer

**Files:**
- Modify: `skills/last30days/scripts/lib/normalize.py:54` (the source→normalizer mapping)

- [ ] **Step 1: Inspect existing pattern**

```bash
grep -n "xiaohongshu\|_normalize_grounding" skills/last30days/scripts/lib/normalize.py | head -20
```

- [ ] **Step 2: Add entry**

In the mapping dict where `"xiaohongshu": _normalize_grounding` lives, add `"bilibili": _normalize_grounding,` next to it.

- [ ] **Step 3: Verify**

```bash
python -c "from skills.last30days.scripts.lib import normalize; print('bilibili' in normalize.NORMALIZERS if hasattr(normalize, 'NORMALIZERS') else 'check manually')"
```
If the dict has a different name, list the module's attributes:
```bash
python -c "from skills.last30days.scripts.lib import normalize; print([k for k in dir(normalize) if not k.startswith('_')])"
```
Expected: the dict named in step 1 contains `"bilibili"`.

### Task 19: `planner.py` — source-type tag

**Files:**
- Modify: `skills/last30days/scripts/lib/planner.py:72`

- [ ] **Step 1: Locate the source-type tag dict**

```bash
grep -n '"xiaohongshu":' skills/last30days/scripts/lib/planner.py
```

- [ ] **Step 2: Add entry**

Next to `"xiaohongshu": {"video", "video_shortform", "social"},`, add:
```python
    "bilibili": {"video", "video_shortform"},
```

(Bilibili long-form video is also `video`; short-form is `video_shortform`. No `"social"` tag — B站 is primarily content, not microblogging.)

- [ ] **Step 3: Verify**

```bash
python -c "from skills.last30days.scripts.lib import planner; print('bilibili in module:', 'bilibili' in open(planner.__file__).read())"
```
Expected: `True`.

### Task 20: `render.py` — display name + enumerations

**Files:**
- Modify: `skills/last30days/scripts/lib/render.py:68` (display name map)
- Modify: `skills/last30days/scripts/lib/render.py:845` (source enumeration)

- [ ] **Step 1: Locate both spots**

```bash
grep -n '"xiaohongshu"' skills/last30days/scripts/lib/render.py
```

- [ ] **Step 2: Add display name**

In the `"xiaohongshu": "Xiaohongshu"` map, add `"bilibili": "Bilibili",` next to it.

- [ ] **Step 3: Add to source enumeration list**

In the list around line 845 (`["hackernews", "bluesky", "truthsocial", "polymarket", "grounding", "xiaohongshu", "github", "digg", "perplexity"]`), insert `"bilibili"` right after `"xiaohongshu"`.

- [ ] **Step 4: Verify**

```bash
grep -n '"bilibili"' skills/last30days/scripts/lib/render.py
```
Expected: 2 matches.

### Task 21: `ui.py` — display, color, ordering

**Files:**
- Modify: `skills/last30days/scripts/lib/ui.py:128` (ordering list)
- Modify: `skills/last30days/scripts/lib/ui.py:143` (display tuple)
- Modify: `skills/last30days/scripts/lib/ui.py:502,546` (availability gate)

- [ ] **Step 1: Inspect xiaohongshu pattern**

```bash
grep -n "xiaohongshu" skills/last30days/scripts/lib/ui.py
```

- [ ] **Step 2: Add to ordering list (~line 128)**

In the source-order list where `"xiaohongshu"` appears, add `"bilibili"` immediately after it.

- [ ] **Step 3: Add display tuple (~line 143)**

In the map shaped `"xiaohongshu": ("Xiaohongshu", "post", "posts", Colors.RED)`, add:
```python
    "bilibili": ("Bilibili", "video", "videos", Colors.MAGENTA),
```

If the Colors enum exposes a hex constant or named pink, prefer that. Otherwise `MAGENTA` is acceptable. If Bilibili pink (`#FB7299`) is desirable and Colors supports custom hex, add it; if not, ship MAGENTA and note in PR description that a hex pink can land in a follow-up after upstream confirms the color system.

- [ ] **Step 4: Add availability gate (~line 502,546)**

Mirror the `has_xiaohongshu` pattern:
```python
has_bilibili = "bilibili" in available_sources
```
And in the conditional block where `has_xiaohongshu` is rendered, add an analogous `if has_bilibili:` block that emits the same kind of summary line.

- [ ] **Step 5: Verify ui imports cleanly**

```bash
python -c "from skills.last30days.scripts.lib import ui"
```
Expected: no errors.

### Task 22: `pipeline.py` — five integration points

**Files:**
- Modify: `skills/last30days/scripts/lib/pipeline.py:43` (import)
- Modify: `skills/last30days/scripts/lib/pipeline.py:62` (alias map)
- Modify: `skills/last30days/scripts/lib/pipeline.py:79` (source list)
- Modify: `skills/last30days/scripts/lib/pipeline.py:127` (availability check)
- Modify: `skills/last30days/scripts/lib/pipeline.py:1025` (dispatcher)

- [ ] **Step 1: Inspect the xiaohongshu pattern at each location**

```bash
grep -n "xiaohongshu" skills/last30days/scripts/lib/pipeline.py
```

- [ ] **Step 2: Import (line ~43)**

In the import block where `xiaohongshu_api,` is listed, add `bilibili,` (sibling). E.g.:
```python
from .lib import (
    ...,
    bilibili,
    xiaohongshu_api,
    ...,
)
```

- [ ] **Step 3: Alias map (line ~62)**

In the alias dict where `"xhs": "xiaohongshu"` lives, add:
```python
    "bili": "bilibili",
```

- [ ] **Step 4: Default source list (line ~79)**

In the tuple/list of web sources that includes `"xiaohongshu"`, add `"bilibili"` adjacent to it.

- [ ] **Step 5: Availability check (line ~127)**

Mirror the xiaohongshu pattern:
```python
if requested_sources and "bilibili" in requested_sources and env.is_bilibili_available(config):
    available.append("bilibili")
```

If the xiaohongshu version is shaped differently (e.g., unconditional inclusion of always-available sources), match that exactly. Read the surrounding 10 lines to choose the right shape.

- [ ] **Step 6: Dispatcher (line ~1025)**

Mirror the xiaohongshu dispatch arm:
```python
if source == "bilibili":
    return bilibili.search_bilibili(
        topic,
        from_date,
        to_date,
        depth=depth,
    )
```
(Argument names must match `search_bilibili`'s signature exactly. No `config` param.)

- [ ] **Step 7: Verify imports and module loads**

```bash
python -c "from skills.last30days.scripts.lib import pipeline; print('ok')"
```
Expected: `ok`.

### Task 23: Smoke test — run full test suite

- [ ] **Step 1: Run all tests touched in this PR**

```bash
pytest tests/lib/test_bilibili.py tests/lib/test_bilibili_wbi.py -v
```
Expected: 31+ passed.

- [ ] **Step 2: Run the full project test suite if available**

```bash
pytest -x -q
```
Expected: no regressions. If existing tests fail because of unrelated upstream flakiness (e.g., live-network tests), filter them:
```bash
pytest -x -q -m "not live"
```

### Task 24: Commit Phase 3

- [ ] **Step 1: Stage**

```bash
git add skills/last30days/scripts/lib/env.py \
        skills/last30days/scripts/lib/normalize.py \
        skills/last30days/scripts/lib/pipeline.py \
        skills/last30days/scripts/lib/planner.py \
        skills/last30days/scripts/lib/render.py \
        skills/last30days/scripts/lib/signals.py \
        skills/last30days/scripts/lib/ui.py
git diff --cached --stat
```
Expected: 7 files modified, ~30-60 added lines total.

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(bilibili): register source in providers, planner, pipeline, ui

Wires the Bilibili adapter into the existing fan-out machinery:
- env.is_bilibili_available (kill-switch via LAST30DAYS_DISABLE_BILIBILI)
- normalize: register source under shared grounding normalizer
- signals: SOURCE_QUALITY['bilibili'] = 0.7 (matches xiaohongshu)
- planner: tag set {'video', 'video_shortform'}
- render: display name 'Bilibili', source enumeration
- ui: ordering, color, availability gate
- pipeline: import, 'bili' alias, source list, availability, dispatcher

After this commit, /last30days <topic> will fan out to Bilibili by
default alongside the existing sources.
EOF
)"
```

---

## Phase 4: Docs (→ Commit 4)

### Task 25: CHANGELOG entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Inspect existing format**

```bash
head -30 CHANGELOG.md
```

- [ ] **Step 2: Add a new entry**

Add at the top (under the `## Unreleased` heading, or whatever the current "next release" section is):
```markdown
### Added
- Bilibili (B站) as a default web source. Searches the public WBI-signed
  endpoint with auto-bootstrapped `buvid3` cookie — no user configuration
  required. Items are ranked by engagement (coins > favorites > likes >
  danmaku > plays). Disable via `LAST30DAYS_DISABLE_BILIBILI=1`.
```

If the project uses Keep-a-Changelog conventions and there is no `## Unreleased` yet, create one above the most recent version.

- [ ] **Step 3: Verify**

```bash
grep -n "Bilibili" CHANGELOG.md
```

### Task 26: Commit Phase 4

- [ ] **Step 1: Stage and commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog entry for bilibili source"
```

- [ ] **Step 2: Verify the 4-commit shape**

```bash
git log --oneline main..HEAD
```
Expected (oldest to newest displayed bottom-to-top):
```
<hash> docs: changelog entry for bilibili source
<hash> feat(bilibili): register source in providers, planner, pipeline, ui
<hash> feat(bilibili): add search adapter with cookie bootstrap
<hash> feat(bilibili): add WBI signing module
```

---

## Phase 5: Manual Smoke Test (Pre-PR Verification)

### Task 27: Live API smoke test

This is a manual gate before opening the PR — verifies the bootstrap + signing chain actually works against production.

- [ ] **Step 1: Run a one-off live search via Python REPL**

```bash
python -c "
from skills.last30days.scripts.lib import bilibili
items = bilibili.search_bilibili('游戏', '2025-01-01', '2026-12-31', depth='quick')
print(f'Got {len(items)} items')
for it in items[:3]:
    print(f\"  [{it['relevance']:.2f}] {it['title'][:60]} | {it['url']}\")
"
```
Expected: 1-10 items printed, with non-empty titles, valid URLs, and relevance scores in (0.05, 1.0].

If this fails with `WBI signature may have rotated`, the upstream signing scheme has changed since this spec — pause and check SocialSisterYi/bilibili-API-collect for updates to the MIXIN_KEY_ENC_TAB or signing algorithm.

If this fails with `cookie bootstrap failed`, the User-Agent may have been flagged. Try a different UA string in `bilibili.py:_USER_AGENT`.

- [ ] **Step 2: (Optional) End-to-end through the CLI**

```bash
python -m skills.last30days.scripts.last30days "长沙麻将" --sources bilibili --depth quick
```
Expected: skill runs to completion, output mentions Bilibili in the source enumeration, at least 1 Bilibili item appears in the brief.

If the CLI flag name is different (`--source` vs `--sources`), check `last30days.py` argparse for the canonical name.

### Task 28: Push and open PR

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/bilibili-adapter
```

- [ ] **Step 2: Open PR upstream**

Open a PR from `gilgamesh1124/last30days-skill-zhcn:feat/bilibili-adapter` against `mvanhorn/last30days-skill:main`. Use the description template:

```markdown
## Summary

Adds Bilibili (B站) as a first-class web source, modeled after the existing `xiaohongshu_api` adapter.

- Data source: Bilibili public web search API (`/x/web-interface/wbi/search/type`), no login or API key required
- WBI signing implemented locally from SocialSisterYi/bilibili-API-collect's public spec
- `buvid3` cookie auto-bootstrapped on first use; cached at module level for the process lifetime
- Engagement formula: `play*1 + like*2 + danmaku*1.5 + favorite*2.5 + coin*3`, clamped to `[0.05, 1.0]`
- Kill switch via `LAST30DAYS_DISABLE_BILIBILI=1`

## Out of scope (planned follow-ups)

- Hot-comment enrichment for the Best Takes section (separate PR)
- Extracting the shared `_to_int` Chinese-numeral parser into `normalize.py` (separate PR, once Weibo/Zhihu adapters land and we have 3 copies)
- SKILL.md user-facing source advertisement (deferred to upstream's discretion)

## Test plan

- [x] `pytest tests/lib/test_bilibili.py tests/lib/test_bilibili_wbi.py` — 31 unit tests, fixture-based
- [x] Manual smoke test: `python -c "from skills.last30days.scripts.lib import bilibili; print(bilibili.search_bilibili('游戏', '2025-01-01', '2026-12-31', depth='quick'))"`
- [x] Existing test suite unaffected
- [ ] (Reviewer) Approve color choice for `ui.py` — using `Colors.MAGENTA` as a placeholder for Bilibili pink `#FB7299`
```

---

## Self-Review Checklist (run after the plan above is executed)

Before clicking "Create pull request":

- [ ] All 4 commits present and atomic (`git log --oneline main..HEAD` shows exactly 4)
- [ ] `pytest tests/lib/test_bilibili.py tests/lib/test_bilibili_wbi.py -v` → all green
- [ ] Live smoke test (Task 27) succeeded
- [ ] No accidental modifications to `xiaohongshu_api.py` (`git diff main -- skills/last30days/scripts/lib/xiaohongshu_api.py` is empty)
- [ ] No modifications to `categories.py` (`git diff main -- skills/last30days/scripts/lib/categories.py` is empty)
- [ ] No modifications to `SKILL.md` (`git diff main -- skills/last30days/SKILL.md` is empty)
- [ ] CHANGELOG entry present
- [ ] PR description filled out per the template above
