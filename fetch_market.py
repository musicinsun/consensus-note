"""Aggregate openly licensed GPU quotes and, when configured, licensed NAND prices."""

import json
import math
import os
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit


DATA = Path(__file__).with_name("market-data.js")
PREFIX = "window.MARKET_PRICES = "
GPU_FEED = "https://raw.githubusercontent.com/adriannutiu/gpu-rental-prices/main/data/"
GPU_SNAPSHOTS = "https://api.github.com/repos/adriannutiu/gpu-rental-prices/contents/data/snapshots"
GPU_ERRATA = "https://gpurentalprices.com/api/errata.json"
GPU_REPOSITORY = "https://raw.githubusercontent.com/adriannutiu/gpu-rental-prices/"
# The live mirror retains 90 snapshots. This revision preserves the first 90.
GPU_EARLY_REF = "c4e232d024dffb3c0363a101d4609a9ed9f38bc0"
KST = timezone(timedelta(hours=9))
MODELS = {
    "h100": {"h100", "h100-sxm", "h100-pcie", "h100-nvl"},
    "h200": {"h200", "h200-sxm", "h200-pcie", "h200-nvl"},
    "b200": {"b200"},
    "a100": {"a100", "a100-sxm", "a100-pcie", "a100-sxm-40", "a100-sxm-80",
             "a100-pcie-40", "a100-pcie-80"},
    "l40s": {"l40s"},
    "4090": {"rtx-4090"},
    "5090": {"rtx-5090"},
}


def get_json(url, bearer=None):
    headers = {"Accept": "application/json", "User-Agent": "consensus-note market monitor"}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def percentile(values, fraction):
    index = (len(values) - 1) * fraction
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def excluded_by_errata(offer, snapshot, corrections):
    return any(
        entry["from"] <= snapshot["date"] <= entry["to"]
        and (entry["gpus"] == "*" or offer["gpu"] in entry["gpus"])
        and ("kinds" not in entry or offer["kind"] in entry["kinds"])
        and ("usd_hr" not in entry or offer["usd_hr"] == entry["usd_hr"])
        and entry.get("snapshot_generated_at", snapshot["generated_at"]) == snapshot["generated_at"]
        for entry in corrections
    )


def gpu_snapshot(data, corrections):
    day = date.fromisoformat(data["date"]).isoformat()
    stamp = datetime.fromisoformat(data["generated_at"]).isoformat(timespec="seconds")
    offers = data["offers"]
    if not isinstance(offers, list) or not offers:
        raise ValueError("Unexpected offer response")
    alias_to_model = {alias: model for model, aliases in MODELS.items() for alias in aliases}
    samples = {model: {} for model in MODELS}
    for offer in offers:
        model = alias_to_model.get(offer.get("gpu"))
        price, provider, checked = (offer.get(k) for k in ("usd_hr", "provider", "fetched_at"))
        if (not model or not positive(price) or not isinstance(provider, str) or provider == "vast"
                or provider.startswith("vast-") or provider.startswith("vast.")
                or offer.get("kind") not in ("on-demand", "secure")
                or offer.get("availability") in ("out-of-stock", "waitlist")
                or not isinstance(checked, str) or checked[:10] != day
                or excluded_by_errata(offer, data, corrections.get(provider, []))):
            continue
        samples[model][provider] = min(price, samples[model].get(provider, price))
    if not any(samples.values()):
        raise ValueError("Offer response had no valid observations")
    points = {}
    for model, providers in samples.items():
        values = sorted(providers.values())
        points[model] = {
            "date": day, "at": stamp, "low": round(values[0], 4) if values else None,
            "p25": round(percentile(values, .25), 4) if values else None, "n": len(values),
        }
    return points


def append_gpu(archive, source, corrections):
    for model, point in gpu_snapshot(source, corrections).items():
        archive["gpu"][model] = same_day(archive["gpu"].get(model, []), point)


def backfill_gpu(archive, corrections):
    urls = {}
    for ref in (GPU_EARLY_REF, "main"):
        listing = get_json(GPU_SNAPSHOTS + "?ref=" + ref)
        if not isinstance(listing, list) or not listing:
            raise ValueError("Unexpected snapshot listing")
        for item in listing:
            name = item["name"]
            if item["type"] == "file" and name.endswith(".json"):
                day = date.fromisoformat(name.removesuffix(".json")).isoformat()
                urls[day] = f"{GPU_REPOSITORY}{ref}/data/snapshots/{name}"
    with ThreadPoolExecutor(max_workers=6) as pool:
        for snapshot in pool.map(get_json, (urls[day] for day in sorted(urls))):
            append_gpu(archive, snapshot, corrections)


def same_day(history, snapshot):
    points = {row["date"]: row for row in history}
    day = snapshot["date"]
    if day not in points or snapshot["at"] >= points[day]["at"]:
        points[day] = snapshot
    return [points[key] for key in sorted(points)[-400:]]


def nand_rows(payload):
    """The licensed feed supplies date, kind, item, price and unit for each observation."""
    if not isinstance(payload, list) or len(payload) > 20000:
        raise ValueError("Unexpected NAND feed")
    out = {}
    for row in payload:
        kind, item, day, price, unit = (row.get(key) for key in ("kind", "item", "date", "price", "unit"))
        if (kind not in ("spot", "contract") or not positive(price)
                or not isinstance(item, str) or not 1 <= len(item.strip()) <= 100
                or not isinstance(unit, str) or not 1 <= len(unit.strip()) <= 30
                or not isinstance(day, str) or len(day) != 10):
            raise ValueError("Invalid NAND observation")
        day = date.fromisoformat(day)
        if day > datetime.now(KST).date():
            raise ValueError("NAND observation has a future date")
        key = (kind, item.strip(), unit.strip(), day.isoformat())
        out[key] = {"kind": key[0], "item": key[1], "unit": key[2], "date": key[3], "price": price}
    return out


def read_archive(path):
    if not path.exists():
        return {"version": 1, "gpuSource": "gpurentalprices", "gpu": {}, "nand": []}
    contents = path.read_text(encoding="utf-8").strip()
    if not contents.startswith(PREFIX) or not contents.endswith(";"):
        raise ValueError("Invalid market archive")
    data = json.loads(contents[len(PREFIX):-1])
    if data["version"] != 1:
        raise ValueError("Unknown market archive version")
    if data.get("gpuSource") != "gpurentalprices":
        data["gpuSource"], data["gpu"] = "gpurentalprices", {}
    return data


def write_archive(path, data):
    content = PREFIX + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    if path.exists() and content == path.read_text(encoding="utf-8"):
        return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     dir=path.parent, delete=False) as handle:
        pending = Path(handle.name)
        handle.write(content)
    try:
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def main():
    archive = read_archive(DATA)
    failures = []
    try:
        corrections = {}
        for entry in get_json(GPU_ERRATA)["entries"]:
            if entry["action"] in {"exclude", "reclassify-spot", "reclassify-marketplace"}:
                corrections.setdefault(entry["provider"], []).append(entry)
        if "--backfill" in sys.argv[1:]:
            backfill_gpu(archive, corrections)
        append_gpu(archive, get_json(GPU_FEED + "latest.json"), corrections)
        print("GPU: " + ", ".join(f"{key} {rows[-1]['n']}" for key, rows in archive["gpu"].items()))
    except (ValueError, KeyError, OSError, TypeError, AttributeError) as error:
        failures.append("gpu")
        print(f"GPU: unavailable ({type(error).__name__})", file=sys.stderr)
    if url := os.environ.get("NAND_FEED_URL"):
        try:
            if urlsplit(url).scheme != "https":
                raise ValueError("Feed must use HTTPS")
            fresh = nand_rows(get_json(url, bearer=os.environ.get("NAND_FEED_TOKEN")))
            rows = nand_rows(archive["nand"])
            rows.update(fresh)
            archive["nand"] = list(rows.values())
            archive["nand"].sort(key=lambda row: (row["date"], row["kind"], row["item"], row["unit"]))
            print(f"NAND: {len(fresh)} licensed observations")
        except (ValueError, KeyError, OSError, TypeError, AttributeError) as error:
            failures.append("nand")
            print(f"NAND: unavailable ({type(error).__name__})", file=sys.stderr)
    write_archive(DATA, archive)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
