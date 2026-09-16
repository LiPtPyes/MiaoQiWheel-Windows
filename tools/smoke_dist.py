"""打包产物自检：启动 dist\\MiaoQiWheel\\MiaoQiWheel.exe，验证真实运行行为。

检查项：
1. 能启动并写出配置文件（说明主流程跑通、托盘已建）
2. 内存占用在目标范围内
3. 第二个实例立刻自动退出（单实例互斥量生效）
4. 退出后无残留进程、无 crash.log

用法：
    python tools/smoke_dist.py                                  # 测 dist\\MiaoQiWheel
    python tools/smoke_dist.py <某处>\\MiaoQiWheel.exe          # 测解压后的副本
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "dist" / "MiaoQiWheel" / "MiaoQiWheel.exe"
EXE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_EXE
CONFIG = Path(os.environ.get("APPDATA", Path.home())) / "MiaoQiWheel" / "settings.json"
CRASH = CONFIG.parent / "crash.log"

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


def working_set_mb(pid: int) -> float:
    handle = kernel32.OpenProcess(0x1000 | 0x0400, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION | VM_READ
    if not handle:
        return -1.0
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / 1024 / 1024
    finally:
        kernel32.CloseHandle(handle)
    return -1.0


def wait_for(predicate, timeout: float, interval: float = 0.3) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def main() -> int:
    if not EXE.exists():
        print(f"[失败] 未找到 {EXE}，请先运行 scripts\\build.bat")
        return 1

    had_config = CONFIG.exists()
    had_crash = CRASH.exists()
    crash_size = CRASH.stat().st_size if had_crash else 0
    results: list[tuple[str, bool, str]] = []

    print(f"启动 {EXE.name} ...")
    process = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
    try:
        ok = wait_for(lambda: CONFIG.exists() or not process_is_alive(process), 20.0)
        results.append(("启动并写配置", ok and process_is_alive(process), str(CONFIG)))

        alive = process_is_alive(process)
        results.append(("进程存活", alive, f"pid={process.pid}"))

        # 刚启动时工作集还没涨起来，等 Qt/字体加载完再取稳定值
        time.sleep(4.0)
        rss = working_set_mb(process.pid) if process_is_alive(process) else -1.0
        results.append(("常驻内存 < 90MB", 0 < rss < 90, f"{rss:.1f} MB 工作集"))

        print("  启动第二个实例（应立刻自动退出）...")
        start = time.time()
        second = subprocess.run([str(EXE)], cwd=str(EXE.parent), timeout=25, capture_output=True)
        elapsed = time.time() - start
        results.append(
            ("单实例：第二个立即退出", second.returncode == 0 and elapsed < 12,
             f"返回码 {second.returncode}，耗时 {elapsed:.1f}s")
        )

        results.append(("第一个实例未受影响", process_is_alive(process), ""))
    finally:
        if process_is_alive(process):
            subprocess.run(["taskkill", "/pid", str(process.pid), "/f"], capture_output=True)
            time.sleep(0.5)

    new_crash = CRASH.exists() and (not had_crash or CRASH.stat().st_size > crash_size)
    results.append(("无崩溃日志", not new_crash, str(CRASH) if new_crash else ""))

    print()
    failures = 0
    for name, ok, detail in results:
        print(f"  [{'通过' if ok else '失败'}] {name}" + (f"  — {detail}" if detail else ""))
        failures += 0 if ok else 1

    if not had_config and CONFIG.exists():
        try:
            CONFIG.unlink()
            print(f"\n（已清理测试生成的 {CONFIG}）")
        except OSError:
            pass

    print(f"\n{'DIST-SMOKE-PASS' if failures == 0 else f'DIST-SMOKE-FAIL ({failures})'}")
    return 0 if failures == 0 else 1


def process_is_alive(process: subprocess.Popen) -> bool:
    return process.poll() is None


if __name__ == "__main__":
    sys.exit(main())
