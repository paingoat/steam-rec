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

### Split (đề xuất): theo thời gian, leave-last-out cho từng user, chỉ tính trên positive
- Sắp positive của mỗi user theo (`date`, `review_id`). Positive cuối → **test**, kế cuối → **validation**, còn lại → **train**.
- Chỉ user có **≥ 3 positive** mới vào eval (EDA: khoảng 3.30M user). User có < 3 positive thì toàn bộ vào train
  và được dùng cho popularity, item stats và CB item features.
- 4.3% user có 2 positive cuối cùng ngày, nên thứ tự giữa chúng do `review_id` quyết định (hợp lệ, ghi chú lại).
- **Chống leakage:** popularity, k-core, IDF và user profile **chỉ tính trên train**. Có test tự động kiểm tra
  `max(train.date) ≤ date(val) ≤ date(test)` cho từng user.

### Lọc k-core trên train positive (đề xuất)
| cấu hình | users | items | interactions | ALS factors rank 64 |
|---|---|---|---|---|
| (user ≥ 1, item ≥ 1) | 12.66M | 37.4k | 35.3M | 3.25 GB |
| **(user ≥ 3, item ≥ 5) — đề xuất mặc định** | 3.30M | 32.7k | 23.7M | 0.85 GB |
| (5, 10) — ablation | 1.62M | 26.1k | 18.0M | 0.42 GB |
| (10, 20) | 0.54M | 17.9k | 11.0M | 0.14 GB |

Ngưỡng là config (`gold.min_user_pos`, `gold.min_item_pos`). Bảng này đo trên toàn bộ positive (trước split),
nên chỉ dùng để định hướng. Gold sẽ tính lại trên train.

### Bảng Gold
Tên bảng và cột dưới đây khớp với code (`src/steam_rec/pipelines/gold.py`, `pipelines/modeling.py`).

| Bảng | Cột |
|---|---|
| `id_map_users` / `id_map_items` | `user_id`/`app_id` → `user_idx`/`item_idx` INT liên tục (ALS yêu cầu INT) |
| `interactions` | user_idx, item_idx, user_id, app_id, date, review_id, hours, confidence, split ∈ {train, val, test} (chỉ positive) |
| `history` | user_idx, item_idx, date, review_id, is_recommended: mọi review (cả negative khi `negatives: mask`) trên user/item của id map; chỉ dùng để mask candidate theo thời điểm |
| `eval_targets` | user eval (sample tất định theo seed, tối đa `eval.max_eval_users`) và target val/test, dùng chung cho mọi model |
| `demo_users` | user_idx: user ngoài eval được precompute top-K cho demo |
| `artifacts/<run_id>/topk` | user_id, app_id, rank, score, model, run_id (kèm `catalog`, `topk_users` cho demo) |

Vector CB (TF-IDF tags ⊕ description) không lưu thành bảng Gold. Chúng được tính trong stage train và lưu ở
`artifacts/<run_id>/models/` (`cb_item_knn.npz`, `cb_x_tag.npz`, `cb_tag_idf.npy`, `cb_tag_vocab.json`).

### Metric
Recall@K và NDCG@K (K = 10, 20) với 1 item test cho mỗi user, catalog coverage@K, và eligible-user coverage
(tỉ lệ eval user mà model trả về đủ K gợi ý). Tune trên **validation**. Chạy test **một lần** cho cấu hình cuối.
