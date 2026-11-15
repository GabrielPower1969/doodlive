"""GPU lock for local Qwen3-TTS runs: /tmp/doodlive_tts.lock (several agents share one Apple GPU).

    with tts_lock.held("voice_joseph gen"):      # waits while another live process holds it
        ...

The file holds `<pid> <who> <iso time>`. It is created atomically (O_EXCL) and removed on exit only when it still
carries this process' pid; another process' lock is never deleted (a lock whose pid is dead is reported and waited on,
not removed: ask its owner).
"""
import contextlib, datetime, os, sys, time

LOCK = "/tmp/doodlive_tts.lock"


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextlib.contextmanager
def held(who="tts", poll=15, max_wait=4 * 3600):
    me = f"{os.getpid()} {who} {datetime.datetime.now().isoformat(timespec='seconds')}\n"
    t0 = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, me.encode()); os.close(fd)
            break
        except FileExistsError:
            try:
                owner = open(LOCK).read().strip()
            except OSError:
                owner = "?"
            pid = int(owner.split()[0]) if owner.split() and owner.split()[0].isdigit() else 0
            print(f"[tts_lock] held by {owner!r} ({'alive' if pid and _alive(pid) else 'pid not running: stale, not removed'}); waiting", file=sys.stderr, flush=True)
            if time.time() - t0 > max_wait:
                sys.exit("[tts_lock] gave up waiting")
            time.sleep(poll)
    try:
        yield
    finally:
        try:
            if open(LOCK).read().startswith(f"{os.getpid()} "):
                os.remove(LOCK)
        except OSError:
            pass
