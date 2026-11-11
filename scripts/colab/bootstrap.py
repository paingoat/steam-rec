# Runs INSIDE the Colab kernel via:  colab exec -s steam-rec-mvp --timeout 900 -f scripts/colab/bootstrap.py
# Precondition: /content/src.tgz uploaded (git archive of a known commit). Idempotent per commit.
import os
import platform
import shutil
import subprocess
import sys
import tarfile

SRC_TGZ, ROOT = "/content/src.tgz", "/content/steam_rec"
from pathlib import Path

sha = Path("/content/src.sha").read_text().strip() if os.path.exists("/content/src.sha") else "unknown"
marker = f"{ROOT}/.src_sha"
if os.path.exists(marker) and Path(marker).read_text().strip() == sha:
    print(f"[bootstrap] code {sha[:7]} already installed")
else:
    shutil.rmtree(ROOT, ignore_errors=True)
    with tarfile.open(SRC_TGZ) as t:
        t.extractall(ROOT, filter="data")
    Path(marker).write_text(sha)
    req = f"{ROOT}/requirements-colab.txt"
    cmd = ["uv", "pip", "install", "--system", "-q", "-r", req] if shutil.which("uv") else \
          [sys.executable, "-m", "pip", "install", "-q", "-r", req]
    subprocess.run(cmd, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "-e", ROOT], check=True)
    print(f"[bootstrap] installed code {sha[:7]}")

os.environ["STEAM_REC_GIT_SHA"] = sha
if ROOT + "/src" not in sys.path:
    sys.path.insert(0, ROOT + "/src")
import pyspark

mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
du = shutil.disk_usage("/content")
java = subprocess.run("java -version 2>&1 | grep -i version | head -1", shell=True, capture_output=True, check=False,
                      text=True).stdout.strip()
print(f"[bootstrap] python {platform.python_version()} cpus={os.cpu_count()} ram_gb={mem:.1f} "
      f"disk_free_gb={du.free / 1e9:.0f} pyspark={pyspark.__version__} java='{java}'")
print("[bootstrap] drive mounted:", os.path.isdir("/content/drive/MyDrive"))
from importlib.metadata import version

print("[bootstrap] versions:", {p: version(p) for p in ("pyspark", "numpy", "scipy", "pandas", "pyarrow",
                                                          "kagglehub", "pydantic", "typer")})
