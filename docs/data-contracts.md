# Data contracts — Steam Recommendation MVP

Status: **ĐÃ DUYỆT ở Gate 2 (2026-11-11)**: k-core 3/5, review tiêu cực → mask, split leave-last-out theo thời gian cho từng user, chạy full trên Colab. Các con số lấy từ `reports/eda/eda_summary.json`
(Bronze snapshot `bronze/kaggle/v28/20261111T020628Z`).

## Bronze (bất biến)
`s3://steam-rec/bronze/kaggle/v28/<ingest_run_id>/raw/{games.csv, games_metadata.json, users.csv, recommendations.csv}`,
kèm `_manifest.json` (size, SHA-256, ingested_at UTC, source URL). `_LATEST` trỏ tới snapshot hợp lệ.
Raw files không bao giờ bị sửa. Ingest lại mà checksum giống hệt thì không làm gì (no-op).

Header của cả 3 file CSV khớp đúng `steam_rec.common.schemas`. Không có giá trị null ở bất kỳ cột nào.

## Silver — `silver/<table>/dataset=v28/run=<run_id>/` (Parquet, zstd)

| Bảng | Grain / PK | Kiểu và chuẩn hóa | Data quality (fail ✖ / warn ⚠) |
|---|---|---|---|
| `games` | `app_id` | `date_release`→DATE; win/mac/linux/steam_deck BOOL; price DOUBLE; `rating` STRING | ✖ PK trùng hoặc null |
| `games_metadata` | `app_id` | `description` trim, rỗng→NULL; `tags` ARRAY<STRING>, rỗng→[] | ✖ app_id không có trong games; ⚠ % description rỗng, % không có tag |
| `game_catalog` | `app_id` | games ⟕ games_metadata (left join) | ✖ số dòng ≠ games |
| `users` | `user_id` | giữ nguyên; `products`/`reviews` chỉ là số liệu mô tả | ✖ PK trùng |
| `recommendations` | `review_id`; natural key (`user_id`,`app_id`) | `date`→DATE (không có giờ, coi là UTC); `hours` FLOAT ∈ [0, 1000] | ✖ review_id trùng, FK app_id/user_id hỏng, hours < 0; ⚠ hours = 0 |

- **Dedup:** (`user_id`,`app_id`) trùng thì giữ dòng có `date` mới nhất, tie-break bằng `review_id` lớn nhất (EDA: 21 cặp trùng).
- **Partition:** `recommendations` theo `year`, khoảng 13 giá trị từ 2010 đến 2022. **Không partition theo user_id.**
- **Kết quả DQ** ghi vào `artifacts/<run_id>/dq/silver_dq.json`. Có lỗi ✖ thì stage fail và không ghi `_SUCCESS`.

## Gold — `gold/<table>/dataset=v28/run=<run_id>/`

### Định nghĩa feedback (đề xuất)
- **Positive** = `is_recommended = true` (85.8% số review).
- **Confidence** = `1 + log1p(hours)`. Nguồn đã cap hours ở 1000, nên không cần cap thêm. `alpha` của ALS được tune riêng.
- **Giả định về `hours` (chốt 2026-11-25):** coi `hours` là số giờ chơi **tại thời điểm viết review** và dùng như tín hiệu tin cậy.
  Caveat đã biết: khoảng 2% review có `hours` > 24 giờ × số ngày từ ngày phát hành, tức một phần dữ liệu giống giờ chơi lúc crawl.
  Sẽ xem lại khi có `playtime_at_review` từ Steam API (backlog).
- **Negative review** không đưa vào ALS (implicit ALS không mô hình hóa được "ghét"). Chúng vẫn được giữ để:
  (a) mask khỏi candidate (không gợi ý lại game user đã review), (b) phân tích riêng.
  Ablation qua config: `negatives: mask | drop`.
- Review chỉ là một lát cắt hành vi: user review một game không có nghĩa là toàn bộ thư viện game của họ.
  Vì vậy metric đo khả năng dự đoán *review tích cực tiếp theo*, không đo "game sẽ chơi".

### Split (v2, 2026-11-25): mốc thời gian chung cho mọi user
Thay cho leave-last-out theo từng user ở v1. Leave-last-out làm rò rỉ thời gian giữa các user: model học review
"tương lai" của user khác.
- Chỉ tính trên positive. **train** = `date < split.t_val`; **val** = `[t_val, t_test)`; **test** = `date ≥ t_test`.
  Hai mốc là config `split.t_val` / `split.t_test`, do chủ dự án chọn từ `reports/eda_time_split.md`.
- **K-core (`gold.min_user_pos=3`, `gold.min_item_pos=5`) chỉ chạy trên train.** Id map của user/item lấy từ train-core.
- Target val/test là **mọi** positive trong cửa sổ, của user thuộc train-core, trên item thuộc train-core (warm).
  Số positive bị loại vì user hoặc item lạnh được ghi trong `stages/gold.json` (`metrics.kcore`).
- Eval user: mỗi split lấy mẫu tất định (hash theo seed), tối đa `eval.max_eval_users` user, dùng chung cho mọi model.
- **Mask** khi chấm một cửa sổ: mọi review (cả negative) có `date < cutoff` của cửa sổ đó.
  **Input** của model là lịch sử train. Model **fit một lần trên train**, nên khi test sẽ không dùng các tương tác
  trong cửa sổ val làm input; refit để ở backlog.
- **Chống leakage:** popularity, k-core, id map và ALS chỉ dùng train (`date < t_val`). IDF của CB chỉ dùng metadata.
  Có test cho trường hợp cắt chung cho mọi user (`tests/unit/test_splits_kcore.py`).

### Bảng Gold
Tên bảng và cột dưới đây khớp với code (`src/steam_rec/pipelines/gold.py`, `pipelines/modeling.py`).

| Bảng | Cột |
|---|---|
| `id_map_users` / `id_map_items` | `user_id`/`app_id` → `user_idx`/`item_idx` INT liên tục (ALS yêu cầu INT) |
| `interactions` | user_idx, item_idx, user_id, app_id, date, review_id, hours, confidence, split ∈ {train, val, test} (chỉ positive) |
| `history` | user_idx, item_idx, date, review_id, is_recommended: mọi review (cả negative khi `negatives: mask`) trên user/item của id map; chỉ dùng để mask candidate theo thời điểm |
| `eval_targets` | user_idx, split ∈ {val, test}, items array<int> (mọi target warm trong cửa sổ), cutoff_date; sample tất định theo seed, tối đa `eval.max_eval_users`/split |
| `demo_users` | user_idx: user ngoài eval được precompute top-K cho demo |
| `artifacts/<run_id>/topk` | user_id, app_id, rank, score, model, run_id (kèm `catalog`, `topk_users` cho demo) |

Vector CB (TF-IDF tags ⊕ description) không lưu thành bảng Gold. Chúng được tính trong stage train và lưu ở
`artifacts/<run_id>/models/` (`cb_item_knn.npz`, `cb_x_tag.npz`, `cb_tag_idf.npy`, `cb_tag_vocab.json`).

### Metric (v2)
Mỗi user có nhiều target. Recall@K = |top-K ∩ rel| / min(K, |rel|).
NDCG@K có IDCG tính trên min(K, |rel|) vị trí. Ngoài ra có catalog coverage@K và eligible-user coverage@K.
Tune trên val, chạy test **một lần**.
