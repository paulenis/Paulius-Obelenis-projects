"""Collect prices from every chain.

    python -m kainos.collect              # all chains
    python -m kainos.collect rimi norfa   # only these
    python -m kainos.collect --reparse    # re-read the last raw files without downloading

Each chain runs on its own: a failure in one never stops the others, and data that
fails validation never replaces the last good data.
"""

import argparse
import shutil
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

from . import storage, validation
from .chains import ALL, BY_NAME
from .http_client import Client
from .models import RawPage

RAW_DIR = storage.DATA_DIR / "raw"
KEEP_RAW_RUNS = 6


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _save_raw(raw_dir, pages):
    raw_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        (raw_dir / page.name).write_text(page.content, encoding="utf-8")


def _load_raw(raw_dir):
    return [RawPage(f.name, f.read_text(encoding="utf-8")) for f in sorted(Path(raw_dir).iterdir())]


def _prune_raw(chain):
    folders = sorted((RAW_DIR / chain).glob("*")) if (RAW_DIR / chain).exists() else []
    for old in folders[:-KEEP_RAW_RUNS]:
        shutil.rmtree(old, ignore_errors=True)


def collect_chain(conn, module, client=None, reparse_dir=None, log=print):
    started = _now()
    raw_dir = Path(reparse_dir) if reparse_dir else RAW_DIR / module.NAME / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = storage.start_run(conn, module.NAME, started, raw_dir)
    try:
        if reparse_dir:
            pages = _load_raw(raw_dir)
        else:
            pages = module.fetch(client or Client())
            _save_raw(raw_dir, pages)
        products = module.parse(pages, today=date.today())
    except Exception as e:  # any surprise in one chain must not stop the rest
        message = f"{type(e).__name__}: {e}"
        storage.finish_run(conn, run_id, "failed", _now(), message=message)
        log(f"  {module.LABEL}: KLAIDA – {message}")
        log(traceback.format_exc(limit=3))
        return "failed"

    previous = storage.last_ok_run(conn, module.NAME)
    problems = validation.check(products, module.MIN_COUNT, previous["product_count"] if previous else None)
    if problems:
        storage.finish_run(conn, run_id, "rejected", _now(), len(products), "; ".join(problems))
        log(f"  {module.LABEL}: ATMESTA – {'; '.join(problems)} (paliekami ankstesni duomenys)")
        return "rejected"

    storage.save_products(conn, run_id, products)
    storage.finish_run(conn, run_id, "ok", _now(), len(products))
    storage.prune_runs(conn, module.NAME)
    if not reparse_dir:
        _prune_raw(module.NAME)
    log(f"  {module.LABEL}: gerai – {len(products)} prekių")
    return "ok"


def collect(chains=None, reparse=False, log=print):
    conn = storage.connect()
    modules = [BY_NAME[c] for c in chains] if chains else ALL
    client = Client()
    results = {}
    log(f"Renkamos kainos ({_now()})")
    for module in modules:
        reparse_dir = None
        if reparse:
            last = storage.last_run(conn, module.NAME)
            if not last or not last["raw_dir"] or not Path(last["raw_dir"]).exists():
                log(f"  {module.LABEL}: nėra išsaugotų failų")
                continue
            reparse_dir = last["raw_dir"]
        results[module.NAME] = collect_chain(conn, module, client, reparse_dir, log)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Surinkti kainas iš tinklų")
    parser.add_argument("chains", nargs="*", help=f"tinklai: {', '.join(BY_NAME)} (numatyta – visi)")
    parser.add_argument("--reparse", action="store_true", help="perskaityti paskutinius išsaugotus failus")
    args = parser.parse_args(argv)
    unknown = [c for c in args.chains if c not in BY_NAME]
    if unknown:
        parser.error(f"nežinomas tinklas: {', '.join(unknown)}")
    results = collect(args.chains or None, args.reparse)
    return 0 if all(r == "ok" for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
