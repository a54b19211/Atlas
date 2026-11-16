"""
拉取常驻服务：按间隔一轮一轮地拉，一轮做完睡到下一轮；收到 SIGTERM / SIGINT 做完当前一页后退出。

    python -m pull.service              # 常驻（systemd 单元样例见 ops/atlas-pull.service）
    python -m pull.service --once       # 只跑一轮就退出
    python -m pull.service --once --source nmpa --max-pages 1

间隔、暂停、立即跑一轮都在库里（atlas_settings 的 pull.*），由管理接口 /api/pull/* 改，服务每几秒看一次。
拉哪些来源：白名单里有启用规则的来源（atlas_pull_whitelist）。
"""
import argparse
import signal
import threading
import time
from contextlib import contextmanager

import httpx
from loguru import logger

from config.settings import APP
from pull import fabric, store

TICK = 5  # 秒：多久看一次停止信号、暂停和“立即跑一轮”


@contextmanager
def fabric_client():
    headers = {"Authorization": f"Bearer {APP.FABRIC_READ_TOKEN}"}
    with httpx.Client(base_url=APP.FABRIC_API_URL, headers=headers, timeout=60) as client:
        client.event_hooks["response"] = [lambda r: r.raise_for_status()]
        yield client


def run_round(stop: threading.Event, only_source: str = "", max_pages: int = 0):
    """一轮：每个启用的来源从记下的序号接着拉。一个来源出错只记下错误，不影响别的来源。"""
    rules = store.list_whitelist()
    gate = store.quality_gate()
    sources = [only_source] if only_source else sorted({r["source_id"] for r in rules if r["enabled"]})
    with fabric_client() as client:
        for source_id in sources:
            if stop.is_set():
                return
            store.mark_run(source_id, started=True)
            error = None
            try:
                def save(rows, next_after, skipped, max_seq, _s=source_id):
                    store.save_page(_s, rows, next_after, skipped, max_seq)
                fabric.pull_source(client, source_id, store.last_seq(source_id), save, rules, gate,
                                   max_pages, should_stop=stop.is_set)
            except Exception as exc:  # 记下来，下一轮从上一页接着拉
                error = f"{type(exc).__name__}: {exc}"[:2000]
                logger.exception(f"[pull] {source_id} 失败")
            store.mark_run(source_id, started=False, error=error)


def run_forever(stop: threading.Event, round_fn=run_round, settings_fn=store.get_settings, clear_run_now=None,
                tick: float = TICK):
    clear_run_now = clear_run_now or (lambda: store.set_settings({"pull.run_now": False}, "pull-service"))
    next_at = 0.0
    while not stop.is_set():
        try:
            s = settings_fn("pull.")
            due = time.monotonic() >= next_at and not s["pull.paused"]
            if due or s["pull.run_now"]:
                if s["pull.run_now"]:
                    clear_run_now()
                round_fn(stop)
                next_at = time.monotonic() + max(int(s["pull.interval_seconds"]), 10)
        except Exception:
            logger.exception("[pull] 一轮没跑成，下个间隔再试")
            next_at = time.monotonic() + 60
        stop.wait(tick)
    logger.info("[pull] 收到停止信号，退出")


def main():
    parser = argparse.ArgumentParser(description="Atlas 从 fabric 拉文档的常驻服务")
    parser.add_argument("--once", action="store_true", help="只跑一轮")
    parser.add_argument("--source", default="", help="只拉这个来源（配合 --once）")
    parser.add_argument("--max-pages", type=int, default=0, help="每个来源最多翻几页（0 = 翻完）")
    args = parser.parse_args()

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    if args.once:
        run_round(stop, args.source, args.max_pages)
    else:
        run_forever(stop)


if __name__ == "__main__":
    main()
