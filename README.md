# Steam Recommendation — Batch MVP

Batch ELT + recommender trên dataset Kaggle **Game Recommendations on Steam v28**
(41.2M review, 14.3M user, 50.9k game). Kiến trúc lake Bronze → Silver → Gold trên **PGSTY SILO** (S3, local).
Spark xử lý trên local (smoke/dev) hoặc trên một VM **Colab** (full). Có 3 model: popularity, implicit ALS
(Spark MLlib) và CB TF-IDF + item-kNN. Demo chạy offline, không cần Colab.

- Kế hoạch và quyết định: `.claude/plans/MVP-BATCH-IMPLEMENTATION-PLAN.md` (local, không push)
- Data contracts: `docs/data-contracts.md` · EDA: `reports/eda.md` · Benchmark: `reports/benchmark.md`
- Vận hành Colab: `docs/runbook-colab.md` + `CLAUDE.md` + skill `.claude/skills/colab-operator/`

## Kết quả (full data, test, 100k user)
| model | Recall@20 | NDCG@20 | catalog coverage@20 | eligible users |
|---|---|---|---|---|
| popularity | 0.0633 | 0.0242 | 0.1% | 100% |
| **ALS** (rank 32, α=5) | **0.1091** | **0.0460** | 2.5% | 100% |
| CB TF-IDF (tags + desc) | 0.0133 | 0.0068 | 79% | 72% |

Chi tiết và các lưu ý (metadata của game phổ biến bị rỗng, grid sửa giữa chừng) ở `reports/benchmark.md`.

## Cài đặt local
```bash
uv sync                                                    # Python 3.13 + PySpark 4.0.5 (Java 17+)
cp infra/silo/.env.example infra/silo/.env && cp .env.example .env   # đặt cùng một mật khẩu dài
docker compose -f infra/silo/docker-compose.yml up -d      # SILO trên 127.0.0.1:9000 (console :9001)
uv run steam-rec storage init                              # tạo bucket steam-rec
```
Kaggle credentials đọc từ `~/.kaggle/kaggle.json` (nằm ngoài repo).

## Pipeline
```bash
uv run steam-rec ingest                         # Kaggle v28 -> bronze + manifest SHA-256 (chạy lại = no-op)
uv run steam-rec eda --scale dev                # reports/eda/eda_summary.json (dữ liệu full, khoảng 5 phút)
uv run steam-rec run all --scale smoke          # silver -> gold -> train -> evaluate -> recommend (khoảng 2 phút)
uv run steam-rec run all --scale dev            # khoảng 1M review (khoảng 5 phút)
uv run steam-rec run train --scale dev --run-id <id>   # resume/extend: stage đã xong sẽ được bỏ qua
uv run steam-rec report                         # reports/benchmark.md
```
Mức **full** chạy trên Colab theo `docs/runbook-colab.md`:
`scripts/colab/bootstrap.py` + `scripts/colab/run_stage.py`, checkpoint vào
`Drive/Research/steam-rec/<run_id>/`. Kết quả trả về qua bundle chunk 45 MB, được import có kiểm tra:
```bash
uv run steam-rec import --bundle-dir data/inbox/<run_id>
```

## Demo offline
```bash
uv run steam-rec demo --user-id 11442391 --model als     # als | cb | popularity
uv run steam-rec demo --tags "RPG,Open World,Souls-like" # cold-start theo tag
uv run steam-rec demo --user-id 1                        # user lạ -> fallback popularity
```

## Tests
```bash
uv run pytest                    # unit (gồm Spark local: split không leakage, k-core, metrics, top-K mask)
uv run pytest -m integration -o addopts=""   # cần SILO đang chạy (boto3 + s3a)
uv run ruff check src scripts tests
```

## Checklist nghiệm thu MVP
- [x] Bronze bất biến + manifest SHA-256; ingest chạy lại là no-op; Bronze trên Colab khớp SHA-256 với Bronze local
- [x] Silver/Gold có DQ report (`artifacts/<run>/dq/`), partition theo năm, không partition theo user_id
- [x] Split theo thời gian cho từng user (leave-last-out), có test chứng minh không leakage; mask = tương tác trước target
- [x] Popularity / ALS / CB có Recall@K, NDCG@K, coverage (K=10, 20) trên cùng tập eval; test chạy một lần
- [x] Top-K và model phục vụ đã import vào SILO, verify SHA-256, restore test đạt
- [x] Demo offline chạy khi không có session Colab nào
- [x] Mọi kết quả gắn `run_id` (timestamp-commit-config hash); `colab sessions` trống sau khi chạy

## Có gì ở đâu
| | Git | SILO (`steam-rec` bucket) | Colab `/content` | Drive `Research/steam-rec/` |
|---|---|---|---|---|
| code, config, docs, report | ✅ | | snapshot `git archive` | |
| raw Kaggle + manifest | | `bronze/` | tạm | |
| silver/gold Parquet | | `silver/`, `gold/` (smoke/dev) | tạm | checkpoint run full |
| model, metrics, top-K | | `artifacts/<run_id>/` | tạm | run full (gồm model ALS đầy đủ) |
| credentials | ❌ | | | |
