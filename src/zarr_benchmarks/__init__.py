
import os
import platform
import subprocess

def clear_cache(path=None):
    # CLEAR_CACHE=fadvise evicts just the files under `path`, which needs no root;
    # CLEAR_CACHE=none skips clearing, for warm-cache runs without sudo.
    if os.environ.get("CLEAR_CACHE") == "none":
        return
    if os.environ.get("CLEAR_CACHE") == "fadvise" and path is not None:
        for root, _, files in os.walk(path):
            for name in files:
                fd = os.open(os.path.join(root, name), os.O_RDONLY)
                try:
                    os.fdatasync(fd)
                    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
                finally:
                    os.close(fd)
        return
    if platform.system() == "Darwin":
        subprocess.run("sync && sudo -n /usr/sbin/purge", shell=True, check=True)
    elif platform.system() == "Linux":
        subprocess.call(['sudo', 'sh', '-c', "sync; echo 3 > /proc/sys/vm/drop_caches"])
    else:
        raise Exception("Unsupported platform")

def time_args():
    if platform.system() == "Darwin":
        return ["gtime", "-v"]
    elif platform.system() == "Linux":
        return ["time", "-v"]
    else:
        raise Exception("Unsupported platform")
