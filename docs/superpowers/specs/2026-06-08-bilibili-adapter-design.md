# Bilibili Adapter for last30days — Design Spec

- **Date**: 2026-06-08
- **Scope**: A single new platform source (`bilibili`) for the last30days skill, intended to be submitted upstream as one PR.
- **Status**: Approved for implementation planning.

---

## 1. Goal & Non-Goals

### Goal
Add Bilibili (B站) as a first-class web source in last30days, on par with the existing `xiaohongshu` adapter. After this PR, `/last30days <topic>` will fan out to Bilibili alongside other sources, returning videos ranked by real user engagement, with no user configuration required.

### Non-Goals
- Microblog (Weibo), Zhihu, Tieba, Douyin, Hupu — each will get its own brainstorming/spec/PR cycle.
- Hot-comment enrichment for "Best Takes" — deferred to a follow-up PR.
- Refactoring `_to_int` / Chinese count parsing into a shared `normalize.py` helper — deferred to a follow-up PR after N≥3 adapters share the pattern.
- SKILL.md user-facing documentation changes — deferred pending upstream review feedback.
- Any change to the `categories.py` topic classifier; it is orthogonal to data-source registration.

---

## 2. Approach

Reuse the upstream Python skeleton: `entity_extract` → `planner` → `pipeline` (fan-out) → `cluster`/`dedupe`/`rerank` → `render`. Add Bilibili as a new platform adapter only.

The adapter strictly mirrors the shape and conventions of `skills/last30days/scripts/lib/xiaohongshu_api.py`:
- Single entry point `search_bilibili(topic, from_date, to_date, depth)` returning a `list[dict]` of normalized web-items.
- Module-level helpers for engagement scoring and Chinese-numeral parsing.
- All HTTP goes through `lib/http.py` so retry / timeout / logging behavior is consistent.

Data acquisition uses **Bilibili's official public web search API directly** — no third-party MCP, no paid aggregator, no user-supplied credentials. The adapter auto-bootstraps a `buvid3` cookie on first use and computes WBI signatures locally.

---

## 3. File Layout

### New files

```
skills/last30days/scripts/lib/
  bilibili.py          # Main adapter: search_bilibili() entry, normalization, scoring
  bilibili_wbi.py      # WBI signing: pure-function helpers, no HTTP, no state

tests/lib/
  test_bilibili.py
  test_bilibili_wbi.py

fixtures/bilibili/
  search_video_response.json    # Sanitized real search response, ~5-10 items
  nav_response.json             # Sanitized /x/web-interface/nav response (for WBI keys)
  v_voucher_response.json       # Failed-signature response shape
```

### Modified files (registration only, ≤10 lines each)

| File | Change |
|---|---|
| `env.py` | Add `is_bilibili_available(config) -> bool`. Returns `True` unless `LAST30DAYS_DISABLE_BILIBILI=1` is set. |
| `normalize.py` | Register `"bilibili": _normalize_grounding` (same normalizer used by xiaohongshu). |
| `pipeline.py` | Import `bilibili`; add alias `"bili": "bilibili"`; add `"bilibili"` to web-source list; availability check; dispatcher case. |
| `planner.py` | Add `"bilibili": {"video", "video_shortform"}` to the source-type tag map. |
| `render.py` | Add display name `"bilibili": "Bilibili"` and include in source enumerations (2 sites). |
| `signals.py` | Add `"bilibili": 0.7` (matches Xiaohongshu's signal weight as a Chinese-language non-English source). |
| `ui.py` | Add display name, Bilibili pink color `#FB7299`, and ordering in `available_sources` rendering. |

Files explicitly **not** touched in this PR: `categories.py`, `SKILL.md`, `xiaohongshu_api.py`.

---

## 4. Adapter Contract

### 4.1 Public entry point

```python
def search_bilibili(
    topic: str,
    from_date: str,         # YYYY-MM-DD
    to_date: str,           # YYYY-MM-DD
    depth: str = "default", # "quick" | "default" | "deep"
) -> list[dict[str, Any]]:
    """Search Bilibili videos and normalize to last30days web-item shape."""
```

### 4.2 Return item schema (matches upstream web-item)

```python
{
    "id": "BILI1",                          # Sequential, "BILI" prefix
    "title": "<视频标题>",
    "url": "https://www.bilibili.com/video/<bvid>",
    "source_domain": "bilibili.com",
    "snippet": "<description, truncated to 500 chars>",
    "date": "2026-05-12",                   # From pubdate epoch
    "date_confidence": "high",              # Always "high" — pubdate is authoritative
    "relevance": 0.612,                     # From _relevance_from_interactions()
    "why_relevant": "Bilibili engagement: play=124k, like=8.2k, danmaku=1.1k, favorite=3.4k, coin=5.6k",
    "engagement": {
        "play": 124000,
        "like": 8200,
        "danmaku": 1100,
        "favorite": 3400,
        "coin": 5600,
        "share": 220,
    },
    "extra": {
        "author": "<UP主昵称>",
        "author_mid": 12345,
        "bvid": "BV1xx...",
        "duration": 245,                    # seconds
    },
}
```

### 4.3 Depth → result-count cap

| Depth | `page_size` requested | Items returned (after filtering) |
|---|---|---|
| `quick` | 10 | up to 10 |
| `default` | 20 | up to 20 |
| `deep` | 30 | up to 30 |

Date-range filter: items with `pubdate` outside `[from_date, to_date]` are dropped client-side.

---

## 5. WBI Signing (`bilibili_wbi.py`)

Pure-function module. No HTTP, no global state, fully unit-testable.

### 5.1 API

```python
MIXIN_KEY_ENC_TAB: list[int] = [...]  # Official 64-byte permutation table, frozen constant.

def get_wbi_keys(nav_json: dict) -> tuple[str, str]:
    """Extract img_key and sub_key from a /x/web-interface/nav response.
    Raises ValueError if the expected fields are missing or malformed."""

def mix_key(img_key: str, sub_key: str) -> str:
    """Apply MIXIN_KEY_ENC_TAB to (img_key + sub_key) → 32-char mixin_key."""

def sign_params(params: dict[str, Any], mixin_key: str, *, ts: int | None = None) -> dict[str, Any]:
    """Return a new dict with wts and w_rid added. Does NOT mutate input.
    If ts is omitted, uses int(time.time()) (injection point for tests)."""
```

### 5.2 Algorithm reference

WBI signing follows the SocialSisterYi/bilibili-API-collect documentation:
1. Build mixin_key by permuting `(img_key + sub_key)` per the published 64-byte table, truncating to 32 bytes.
2. Inject `wts = int(time.time())` into params.
3. Sort params by key, URL-encode each value, join as `k1=v1&k2=v2&...`.
4. Append `mixin_key`, MD5 the result, hex-digest → `w_rid`.

### 5.3 Robustness

- Mutation safety: `sign_params` operates on a shallow copy.
- Failure mode: any malformed input raises `ValueError`. The caller in `bilibili.py` translates that into `http.HTTPError("Bilibili: WBI signing failed: <reason>")`.

---

## 6. Cookie Bootstrap

`buvid3` is required by the search endpoint but obtainable without login.

### 6.1 Bootstrap sequence (one-time per process)

1. `GET https://www.bilibili.com/` with a desktop-Chrome UA (must not contain `curl`, `python`, or `awa`).
2. Extract `buvid3` from `Set-Cookie`.
3. `GET https://api.bilibili.com/x/web-interface/nav` with `cookies={"buvid3": ...}`.
4. Parse the response, run `get_wbi_keys()` → `mix_key()` → cache `mixin_key` and the cookie jar at module level.

### 6.2 Caching

```python
_mixin_key_cache: str | None = None
_cookie_jar_cache: dict[str, str] | None = None
```

Cached for the lifetime of the Python process. Not persisted to disk (no side effects between runs). Subsequent `search_bilibili()` calls in the same process skip the bootstrap.

### 6.3 Failure mode

If any step fails (network, non-200, unexpected JSON shape), raise `http.HTTPError("Bilibili: cookie bootstrap failed: <reason>")`. The pipeline catches it, logs a warning, drops `bilibili` from `available_sources` for this run, and surfaces "Bilibili 暂不可用" in the UI via the existing `ui.py` rendering path.

---

## 7. Engagement Scoring

### 7.1 Formula

```python
weighted = (
    play * 1.0 +
    like * 2.0 +
    danmaku * 1.5 +
    favorite * 2.5 +
    coin * 3.0
)
score = round(min(1.0, max(0.05, weighted / 50_000.0)), 3)
```

### 7.2 Rationale

- `play` is the broadest, weakest signal (passive); base weight 1.0.
- `like` is a light affirmation; 2.0.
- `danmaku` (bullet comments) is participation, a Bilibili-specific cultural signal; 1.5.
- `favorite` indicates retention intent; 2.5.
- `coin` is Bilibili's strongest engagement signal — users have a finite weekly coin budget, so spending one is a meaningful endorsement; 3.0.
- `share` and `comment` are kept in the `engagement` dict for downstream consumers but excluded from the scoring formula to avoid double-counting virality (already implicit in `play`) and noise (comments include negativity).
- Denominator `50_000` calibrated so a moderately popular video (~100k plays, ~3k likes, healthy engagement) scores around 0.5; viral videos approach 1.0.

### 7.3 Chinese-numeral parsing

The B站 web API returns counts as integers (unlike Xiaohongshu's strings). However, defensively handle string forms via a private `_to_int()` that supports plain ints, `1.2万`, and `3亿` — same shape as `xiaohongshu_api._to_int`. This duplication is intentional for this PR; consolidation into `normalize.py` is a follow-up.

---

## 8. Error Handling Summary

| Layer | Failure | Behavior |
|---|---|---|
| `bilibili_wbi.sign_params` | Malformed input | `ValueError` |
| `bilibili._ensure_session` | Network / non-200 / bad JSON | Wrap as `http.HTTPError` |
| `bilibili.search_bilibili` | Search returns `v_voucher` | Log "WBI signature may have rotated", raise `http.HTTPError` |
| `bilibili.search_bilibili` | Search returns `code != 0` | Raise `http.HTTPError` with code and message |
| `bilibili.search_bilibili` | Search returns empty result list | Return `[]` (not an error) |
| Pipeline dispatcher | Any of the above | Log warning, drop source, show "Bilibili 暂不可用" via existing UI path |

Rate limiting: a single run issues at most 1 bootstrap (~2 HTTP calls, cached) + 1 search. Far below B站's empirical ~1 req/s threshold. No client-side rate limiter; rely on `http.py`'s built-in retry-on-412 for one-shot backoff.

---

## 9. Testing

All tests are fixture-based. **No live network calls in CI.**

### 9.1 Test inventory

`tests/lib/test_bilibili_wbi.py`:
1. `test_mix_key_produces_official_example_output`
2. `test_sign_params_with_fixed_ts_matches_known_w_rid`
3. `test_sign_params_does_not_mutate_input`
4. `test_get_wbi_keys_extracts_from_nav_response`
5. `test_get_wbi_keys_raises_on_missing_field`

`tests/lib/test_bilibili.py`:
6. `test_to_int_handles_plain_int`
7. `test_to_int_handles_wan_yi_suffix`
8. `test_to_int_handles_garbage`
9. `test_relevance_clamped_to_range`
10. `test_relevance_weights_coin_above_favorite_above_like_above_play`
11. `test_search_bilibili_normalizes_fixture_response`
12. `test_search_bilibili_filters_by_date_range`
13. `test_search_bilibili_respects_depth_caps`
14. `test_search_bilibili_raises_on_v_voucher`
15. `test_search_bilibili_handles_empty_result_list`
16. `test_ensure_session_caches_across_calls`

Target: ensure the adapter runs end-to-end against fixtures. Coverage is not pursued as a number; passing tests + fixture realism is the bar.

### 9.2 Live smoke test

Add one test under `tests/integration/test_bilibili_live.py` gated by `@pytest.mark.live`, skipped in CI. Hits the real API once with topic `"游戏"` to verify the bootstrap + signing chain still works against production. Manual `pytest -m live` invocation only.

---

## 10. PR Plan

### 10.1 Branch

`feat/bilibili-adapter` off `main`.

### 10.2 Commit sequence (4 atomic commits)

1. **`feat(bilibili): add WBI signing module`**
   `bilibili_wbi.py` + `test_bilibili_wbi.py` + `fixtures/bilibili/nav_response.json`

2. **`feat(bilibili): add search adapter with cookie bootstrap`**
   `bilibili.py` + `test_bilibili.py` + `fixtures/bilibili/search_video_response.json` + `fixtures/bilibili/v_voucher_response.json`

3. **`feat(bilibili): register source in providers, planner, pipeline, ui`**
   The 7 small registration edits listed in §3.

4. **`docs: changelog entry for bilibili source`**
   `CHANGELOG.md` only.

### 10.3 PR description content

- Data source: Bilibili public web search API, no login required.
- WBI signing implemented locally per SocialSisterYi's public spec.
- `buvid3` auto-bootstrap, zero user configuration.
- Engagement formula and weight rationale (linkable to §7).
- Alignment with `xiaohongshu_api.py` conventions; intentional differences explained.
- Test surface: 16 unit tests, fixture-based.
- Out of scope (and listed as future follow-ups):
  - Hot-comment enrichment for Best Takes
  - Shared `parse_chinese_count` helper in `normalize.py`
  - SKILL.md surface-level mention

### 10.4 Acceptance criteria

- `pytest tests/lib/test_bilibili.py tests/lib/test_bilibili_wbi.py` passes.
- A manual run of `python -m skills.last30days.scripts.last30days "游戏"` (or equivalent CLI entry) lists `bilibili` in the executed sources and includes at least 1 Bilibili item in the brief when results exist.
- No regressions in existing tests.

---

## 11. Follow-up Work (Not in This PR)

1. **Hot-comment enrichment** — additional API call per top-N video, feeds "Best Takes" section. Separate PR.
2. **`parse_chinese_count` shared helper** — once Weibo / Zhihu adapters land, consolidate the three private `_to_int` copies into `normalize.py`.
3. **Weibo adapter** — separate brainstorming, spec, PR.
4. **Zhihu adapter** — separate brainstorming, spec, PR.
5. **SKILL.md updates** — after upstream signals acceptance, add Bilibili to the user-facing source list.
