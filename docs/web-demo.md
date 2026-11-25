# Web demo — bàn giao cho người làm web

> Đọc file này trước khi làm phần web. Phần web là **tạm thời**: nó chỉ là một lớp vỏ quanh demo offline.
> Thiết kế chính là pipeline batch trong `src/steam_rec/` (Bronze → Silver/Gold → model → top-K) và sẽ còn được scale tiếp.

## Tình hình hiện tại (2026-11-22)

- Run full mới nhất (v2, 2026-11-25): `20261125T045027Z-dbf308a-v2full`. Run này dùng split theo mốc thời gian chung, metadata
  đã bổ sung (tags cho các game lớn như TF2, Witcher 3…), và gồm 3 model ALS rank 32, CB TF-IDF, popularity.
  Run v1 cũ `20261111T030116Z-3ef4284-e0820c90` vẫn còn trên HF.
  Metrics xem ở `reports/benchmark.md`.
- Git chỉ chứa code, config và report. **Dữ liệu không nằm trong git** (`data/` đã gitignore):
  - Silver/Gold full và checkpoint nằm trên Google Drive của chủ dự án. Web **không cần** phần này.
  - Những gì demo cần (top-K precomputed, catalog, model nhỏ cho cold-start) nằm trong một bundle trên (v2 khoảng 113 MB, v1 khoảng 65 MB)
    HF Hub, ở dataset **public** `paingoat/steam-rec-demo`, thư mục `bundles/<run_id>/`. Bundle gồm các tar part và
    `bundle_manifest.json` (SHA-256), đúng định dạng mà pipeline export ra.
- Môi trường `demo` (`configs/demo.yaml`) dùng lake là thư mục `data/lake/` nên **không cần MinIO/SILO, Spark, Colab
  hay `.env`**.

## Setup (một lần)

```bash
uv sync                                   # Python 3.13, giống pipeline
uv run --with huggingface_hub python scripts/demo/fetch_bundle.py        # tải run mới nhất (không cần token) -> verify SHA-256 -> data/lake
uv run steam-rec demo --env demo --user-id 378 --model als               # kiểm tra nhanh (user có top-K ở run v2)
uv run steam-rec demo --env demo --tags "RPG,Open World" -k 5            # cold-start theo tag
```

Luôn truyền `--env demo`. Nếu thiếu, env mặc định là `local`, sẽ cố kết nối S3/MinIO ở `127.0.0.1:9000` và báo lỗi.
Khi có run mới trên HF, chạy lại `fetch_bundle.py`. `Demo` tự chọn run full mới nhất có trong lake; muốn cố định run
thì truyền `run_id`.

## Dùng demo trong web

Gọi `Demo` như một thư viện. Không gọi CLI qua subprocess, và **khởi tạo một lần khi app start** (lần đầu sẽ copy
parquet sang `data/cache/<run_id>/`, các lần sau mất khoảng 0.4 s):

```python
from steam_rec.common.config import load_config
from steam_rec.serving.demo import Demo
from steam_rec.storage.store import get_store

cfg = load_config("demo")
demo = Demo(cfg, get_store(cfg), run_id=None, k=10)   # k cố định theo instance

demo.for_user(378, model="als")           # model: "als" | "cb" | "popularity"; mỗi lần gọi ~40 ms
demo.for_user(123, exclude_app_ids=[730, 570])  # user lạ: fallback popularity bỏ các game user đã review
demo.for_new_user(["RPG", "Open World"])  # cold-start theo tag
```

Output là `dict`:

| key | có khi | ý nghĩa |
|---|---|---|
| `mode` | luôn có | `precomputed:<model>`, `fallback:popularity (history-masked)` (user không có top-K, đã loại `exclude_app_ids`), `fallback:popularity (no history)` (user hoàn toàn mới), `cold-start:tags`, `fallback:popularity (no known tags)` |
| `items` | luôn có | list gồm `rank, app_id, title, score, rating, tags (≤5), source` (`source` có thể là `popularity-backfill` khi CB thiếu item) |
| `user_id` | `for_user` | |
| `run_id` | `for_user` có top-K | |
| `unknown_tags` | `cold-start:tags` | những tag không có trong vocab |

`exclude_app_ids` (tùy chọn): danh sách `app_id` user đã review/sở hữu mà web biết (ví dụ lịch sử tương tác trên web).
Top-K precomputed đã tự mask toàn bộ lịch sử của user trong dataset; với user **không** có top-K, demo không có lịch sử
của họ, nên web cần truyền `exclude_app_ids` để fallback không gợi ý lại game đã review. CLI: `--exclude 730,570`.

Dữ liệu tham chiếu có sẵn trên object (chỉ đọc):
- `demo.known`: tập `user_id` có top-K precomputed (run v2: 180 362 user; run v1: 102 000), dùng để gợi ý user mẫu hoặc autocomplete. Ví dụ với run v2: `378`, `671`, `694`, `856`.
- `demo.catalog`: DataFrame 32 692 game, index `item_idx`, các cột `app_id, title, rating, positive_ratio, price_final, tags`.
- `demo.tag_vocab`: 441 tag đã chuẩn hóa (lowercase, `_` thay cho space/`-`), dùng cho UI chọn tag.
- Ảnh game: dùng URL công khai của Steam theo `app_id`, ví dụ
  `https://cdn.cloudflare.steamstatic.com/steam/apps/<app_id>/header.jpg` (không có trong bundle).

## Quy tắc cho phần web (bắt buộc)

1. **Code web nằm riêng** trong thư mục `web/` ở gốc repo (backend, frontend, Dockerfile nếu có). Không đặt vào
   `src/steam_rec/`.
2. **Không sửa code gốc** (`src/steam_rec/`, `configs/` ngoài `demo.yaml`, `scripts/colab/`, `tests/`). Chỉ import
   `steam_rec.serving.demo.Demo` và các helper config/store như ví dụ ở trên. Nếu thực sự cần API mới (ví dụ
   tìm game theo tên, phân trang), viết adapter trong `web/`. Nếu adapter không đủ thì mở issue/PR riêng để chủ dự án
   quyết định, không vá thẳng vào core.
3. **Dependency của web không đưa vào `[project].dependencies`.** Dùng dependency group riêng
   (`uv add --group web fastapi uvicorn ...`, chạy bằng `uv run --group web ...`) hoặc `package.json` riêng cho frontend.
4. **Không commit dữ liệu hay token**: không commit `data/`, bundle, `.env`, HF token. Dữ liệu chỉ lấy qua
   `fetch_bundle.py`.
5. Phần web không được làm hỏng `uv run pytest` và `uv run ruff check src tests`.

## Dành cho chủ dự án: phát hành bundle mới

Sau khi import một run mới (`uv run steam-rec import --bundle-dir data/inbox/<run_id>`):

```bash
conda run -n research python scripts/demo/publish_bundle.py <run_id>   # cần HF token có quyền ghi (env research đã có)
```

Lệnh này chỉ upload các tar part và manifest lên `bundles/<run_id>/`. Repo HF ở chế độ **public**: ai cũng tải được mà
không cần token. Vì vậy chỉ đưa lên artifacts phục vụ demo, không đưa silver/gold hay dữ liệu thô.
