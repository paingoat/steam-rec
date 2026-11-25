# Nghiên cứu: tích hợp Apache Iceberg cho lake steam-rec

Trạng thái: **nghiên cứu, chưa triển khai** (2026-11-25). PoC đã đưa vào backlog.
Mục tiêu: bỏ cơ chế versioning tự quản (`run=<run_id>` trong đường dẫn, `_LATEST`, marker `_SUCCESS`/stage) và dùng
table format chuẩn. Table format lo transaction, snapshot/time-travel và schema evolution.

## 1. Hiện trạng và điểm đau
| Hiện tại | Vấn đề |
|---|---|
| Bronze: `bronze/kaggle/v28/<ingest_run_id>/raw/*` + `_manifest.json` + `_LATEST` | Ổn với file thô bất biến. **Giữ nguyên.** Iceberg không cần cho Bronze |
| Silver/Gold: `silver/<table>/dataset=v28/run=<run_id>/` (Parquet ghi đè theo thư mục) | Mỗi run là một bản copy đầy đủ (vài GB). Không có atomic commit: ghi dở thì thư mục hỏng. "Bản mới nhất" phải suy ra từ `artifacts/<run_id>/stages/*.json` |
| Đổi schema (ví dụ `game_catalog` thêm `genres`, `tags_src`… ở v2) | Dựa vào code đọc tự kiểm tra `if col in df.columns`, không có lịch sử schema |
| So sánh run cũ/mới | Phải giữ cả hai thư mục; không có time-travel theo thời điểm |

## 2. Iceberg giải quyết gì
- **Atomic commit + snapshot:** mỗi lần ghi tạo một snapshot. Lỗi giữa chừng thì không có snapshot mới. Đọc lại bản cũ bằng
  `VERSION AS OF <snapshot_id>` / `TIMESTAMP AS OF`.
- **Tag/branch:** gắn tag `run_<run_id>` cho snapshot mà một run tạo ra để thay cho thư mục `run=<run_id>`, ví dụ
  `ALTER TABLE … CREATE TAG`. Branch dùng để thử nghiệm (ví dụ `split_v2`) mà không ảnh hưởng `main`.
- **Schema evolution** theo column id: thêm hoặc đổi tên cột mà không phải viết lại dữ liệu cũ.
- **Hidden partitioning:** `recommendations` partition theo `years(date)` mà không cần cột `year` vật lý.
- **Maintenance:** `expire_snapshots`, `rewrite_data_files` (compaction), `remove_orphan_files`.

## 3. Tương thích phiên bản (phải xác minh khi làm PoC)
- Repo dùng **PySpark 4.0.5 / Scala 2.13 / Java 17+**. Iceberg hỗ trợ Spark 4.0 từ dòng **1.10.x** qua artifact
  `org.apache.iceberg:iceberg-spark-runtime-4.0_2.13:<ver>` (jar khoảng 40–50 MB, < 100 MB nên tải được qua 4G).
  **Cần kiểm tra bản mới nhất trên Maven Central khi bắt đầu PoC.**
- Đọc S3/MinIO: dùng `iceberg-aws-bundle` (S3FileIO), hoặc tiếp tục dùng `hadoop-aws` (S3A) đang có qua `HadoopFileIO`.
  Với MinIO nên dùng S3A cho nhất quán với cấu hình `common/spark.py` hiện tại.
- `pyiceberg` (Python thuần) đọc được bảng Iceberg không cần Spark. Có thể dùng cho demo/serving để đọc catalog nhỏ thay
  cho pyarrow trên thư mục.

## 4. Chọn catalog
| Catalog | Local (MinIO SILO) | Colab (filesystem `/content` + Drive) | Nhận xét |
|---|---|---|---|
| **Hadoop catalog** (metadata trong warehouse) | ✅ `s3a://steam-rec/warehouse` | ✅ `file:///content/work/lake/warehouse` | Không cần dịch vụ. Commit dựa trên rename nên **không an toàn với nhiều writer đồng thời**, nhưng ở đây chỉ có một writer. Mirror cả thư mục lên Drive là đủ (metadata nằm cùng chỗ). **Đề xuất cho giai đoạn đầu.** |
| JDBC/SQL catalog (SQLite file) | ✅ | ⚠️ file SQLite phải mirror cùng warehouse | Thêm một file trạng thái; lợi ích nhỏ khi chỉ có một writer |
| REST catalog (Polaris/Lakekeeper/Nessie) | ✅ chạy thêm 1 container trong `infra/silo` | ❌ VM Colab không truy cập được catalog local | Hợp khi có Airflow và nhiều writer; để sau |
| Hive Metastore / Glue | quá nặng / cần AWS | ❌ | Không phù hợp quy mô hiện tại |

## 5. Ánh xạ đề xuất
- Namespace `steam.silver`, `steam.gold`. Bảng `silver.recommendations` (partition `years(date)`), `silver.game_catalog`,
  `silver.users`, `gold.interactions` (partition `split`), `gold.history`, `gold.eval_targets`, `gold.id_map_*`.
- Mỗi stage ghi bằng `df.writeTo(tbl).createOrReplace()` (hoặc `overwritePartitions()`), rồi tạo tag `run_<run_id>` ngay sau commit.
  `artifacts/<run_id>/stages/<stage>.json` ghi thêm `snapshot_id` để truy vết.
- `Ctx.read(key)` / `Ctx.write(df, key)` trong `pipelines/runner.py` là điểm thay thế duy nhất. Thêm `storage.table_format:
  parquet | iceberg` để chuyển dần từng bảng. Code của các stage gần như không phải đổi.
- Artifacts (model `.npy/.npz`, top-K, bundle) **giữ dạng file**. Iceberg chỉ dành cho bảng dữ liệu.
- Colab: warehouse nằm dưới lake trên `/content`, mirror lên Drive như hiện tại. Restore = copy lại thư mục. Đường dẫn trong
  metadata là tuyệt đối, nên **phải giữ cùng URI warehouse giữa các VM** (`file:///content/work/lake/warehouse`).
  Đưa dữ liệu về local thì cần `register_table` hoặc rewrite đường dẫn, và đây là rủi ro chính.

## 6. Rủi ro và chi phí
- Đường dẫn tuyệt đối trong metadata khiến di chuyển giữa Colab và local (MinIO) không trong suốt. Cách giảm: chỉ mang về
  local các bảng nhỏ hoặc artifacts (như hiện nay), hoặc dùng `rewrite_table_path` (procedure có từ Iceberg 1.8+, cần xác minh).
- Thêm jar runtime vào Spark (`spark.jars.packages`), làm thời gian bootstrap Colab tăng khoảng 30 giây.
- Không giải quyết được giới hạn tài nguyên hay tốc độ ALS. Lợi ích chủ yếu là quản lý dữ liệu và tính tái lập.

## 7. Lộ trình đề xuất
1. **PoC (backlog, khoảng 0.5 ngày):** Hadoop catalog trên filesystem local, scale smoke chạy trên Colab. Ghi
   `silver.recommendations` và `silver.game_catalog` dưới dạng Iceberg, tạo tag theo run, đọc lại bằng time-travel, thêm cột
   (schema evolution). So dung lượng và thời gian với Parquet.
2. Thêm cờ `storage.table_format` vào `Ctx.read/write`, chuyển Silver rồi đến Gold. Giữ Parquet làm mặc định cho tới khi
   run full chạy ổn.
3. Khi có crawler Steam API và Airflow (nhiều writer, chạy định kỳ): chuyển sang REST catalog chạy cùng `infra/silo`.
