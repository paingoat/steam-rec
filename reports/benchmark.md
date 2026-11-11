# Benchmark — Steam Recommendation MVP

Spark `local[*]` trên **một máy** (đa nhân, không phải cluster). Thời gian là wall-clock của từng stage.

## Quy mô và thời gian

| run | nơi chạy | scale | users | items | train interactions | eval users | silver (s) | gold (s) | train (s) | evaluate (s) | recommend (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `20261111T023229Z-8c56833-dirty-bcadc979` | local | smoke | 7,061 | 1,912 | 31,991 | 5,000 | 99.8 | 7.1 | 20.0 | 3.7 | 6.7 |
| `20261111T023559Z-7b0b390-33e337bc` | local | dev | 78,680 | 7,439 | 393,481 | 20,000 | 113.2 | 19.5 | 135.8 | 19.7 | 8.0 |
| `20261111T030116Z-3ef4284-e0820c90` | colab | full | 3,303,525 | 32,692 | 17,081,075 | 100,000 | 181.7 | 165.9 | 1331.2 | 49.7 | 27.6 |

## Test metrics — `20261111T023229Z-8c56833-dirty-bcadc979` (smoke)

Cấu hình chọn trên validation (ndcg@20): ALS `{'rank': 16, 'regParam': 0.1, 'alpha': 10.0, 'maxIter': 5}`, CB `{'w_tag': 1.0, 'w_desc': 0.3, 'neighbors': 100}`. Test chỉ chạy **một lần**.

| model | Recall@10 | NDCG@10 | Recall@20 | NDCG@20 | catalog cov@20 | eligible users@20 |
|---|---|---|---|---|---|---|
| popularity | 0.0404 | 0.0186 | 0.0764 | 0.0276 | 0.017 | 1.000 |
| cb | 0.0142 | 0.0086 | 0.0206 | 0.0101 | 0.740 | 0.672 |
| als | 0.0408 | 0.0197 | 0.0730 | 0.0277 | 0.310 | 1.000 |

<details><summary>Validation grid</summary>

| model | params | NDCG@20 | Recall@20 |
|---|---|---|---|
| popularity | `{}` | 0.0349 | 0.0934 |
| cb | `{'w_desc': 0.3}` | 0.0163 | 0.0332 |
| als | `{'rank': 16, 'regParam': 0.1, 'alpha': 10.0, 'maxIter': 5}` | 0.0366 | 0.0898 |

</details>

## Test metrics — `20261111T023559Z-7b0b390-33e337bc` (dev)

Cấu hình chọn trên validation (ndcg@20): ALS `{'rank': 64, 'regParam': 0.1, 'alpha': 10.0, 'maxIter': 10}`, CB `{'w_tag': 1.0, 'w_desc': 1.0, 'neighbors': 100}`. Test chỉ chạy **một lần**.

| model | Recall@10 | NDCG@10 | Recall@20 | NDCG@20 | catalog cov@20 | eligible users@20 |
|---|---|---|---|---|---|---|
| popularity | 0.0335 | 0.0173 | 0.0660 | 0.0254 | 0.005 | 1.000 |
| cb | 0.0127 | 0.0078 | 0.0166 | 0.0088 | 0.890 | 0.709 |
| als | 0.0654 | 0.0341 | 0.1007 | 0.0430 | 0.204 | 1.000 |

<details><summary>Validation grid</summary>

| model | params | NDCG@20 | Recall@20 |
|---|---|---|---|
| popularity | `{}` | 0.0316 | 0.0817 |
| cb | `{'w_desc': 0.0}` | 0.0112 | 0.0221 |
| cb | `{'w_desc': 0.3}` | 0.0116 | 0.0226 |
| cb | `{'w_desc': 1.0}` | 0.0129 | 0.0243 |
| als | `{'rank': 32, 'regParam': 0.1, 'alpha': 10.0, 'maxIter': 10}` | 0.0541 | 0.1263 |
| als | `{'rank': 32, 'regParam': 0.1, 'alpha': 40.0, 'maxIter': 10}` | 0.0433 | 0.1054 |
| als | `{'rank': 64, 'regParam': 0.1, 'alpha': 10.0, 'maxIter': 10}` | 0.0582 | 0.1313 |
| als | `{'rank': 64, 'regParam': 0.1, 'alpha': 40.0, 'maxIter': 10}` | 0.0483 | 0.1134 |

</details>

## Test metrics — `20261111T030116Z-3ef4284-e0820c90` (full)

Cấu hình chọn trên validation (ndcg@20): ALS `{'rank': 32, 'regParam': 0.1, 'alpha': 5.0, 'maxIter': 10}`, CB `{'w_tag': 1.0, 'w_desc': 1.0, 'neighbors': 100}`. Test chỉ chạy **một lần**.

| model | Recall@10 | NDCG@10 | Recall@20 | NDCG@20 | catalog cov@20 | eligible users@20 |
|---|---|---|---|---|---|---|
| popularity | 0.0330 | 0.0166 | 0.0633 | 0.0242 | 0.001 | 1.000 |
| cb | 0.0101 | 0.0060 | 0.0133 | 0.0068 | 0.792 | 0.718 |
| als | 0.0689 | 0.0359 | 0.1091 | 0.0460 | 0.025 | 1.000 |

<details><summary>Validation grid</summary>

| model | params | NDCG@20 | Recall@20 |
|---|---|---|---|
| popularity | `{}` | 0.0303 | 0.0796 |
| cb | `{'w_tag': 1.0, 'w_desc': 0.3, 'neighbors': 100}` | 0.0095 | 0.0175 |
| cb | `{'w_tag': 1.0, 'w_desc': 1.0, 'neighbors': 100}` | 0.0106 | 0.0194 |
| als | `{'rank': 32, 'regParam': 0.1, 'alpha': 5.0, 'maxIter': 10}` | 0.0627 | 0.1421 |
| als | `{'rank': 32, 'regParam': 0.1, 'alpha': 10.0, 'maxIter': 10}` | 0.0613 | 0.1398 |

</details>

## Ghi chú về run full (`20261111T030116Z-3ef4284-e0820c90`)
- **Phần cứng:** Colab CPU High-RAM, 8 vCPU, 54.8 GB RAM, Spark `local[*]` (driver 38 GB). Đây là một máy đơn, **không phải cluster**.
  Chi phí của cả run (ingest + ETL + train + eval + export) là **0.56 CU** (0.26 CU/giờ).
- **Train qua nhiều lần `exec`:** cột "train (s)" chỉ là lần `exec` cuối (fit thứ 2 + chọn model).
  Tổng thực tế: popularity 16 giây, CB 91 giây (2 cấu hình), ALS 2 lần fit × khoảng 21.7 phút.
- **Grid ALS sửa giữa chừng:** grid ban đầu (rank 64/128) quá chậm trên 8 nhân. Fit rank 64 đầu tiên chạy hơn 28 phút
  với 128 ALS block. Theo quyết định của người dùng (2026-11-11), grid full đổi thành **rank 32, alpha ∈ {5, 10}**,
  commit `dcb1c81`. `config.resolved.yaml` của run vẫn ghi grid cũ vì nó được ghi lúc chạy silver. Grid thực tế đã đánh giá
  nằm trong `metrics/validation.json`. Số ALS block cũng giảm từ 128 xuống 16 (2 × số nhân).
- **Rank không phải nút thắt:** fit rank 32 vẫn mất khoảng 22 phút. Chi phí chính là shuffle/checkpoint 17M tương tác × 10 vòng
  trên một máy, không phải rank³.
- **CB bị giới hạn bởi dữ liệu:** trong `games_metadata.json` của v28, nhiều game phổ biến nhất (TF2, Witcher 3, CS:GO,
  Destiny 2…) có `tags` và `description` rỗng. Vì vậy CB chỉ trả đủ K gợi ý cho 72% user đánh giá, và có Recall thấp.
  Đổi lại, CB có catalog coverage cao nhất (79% so với 2.5% của ALS). Demo bổ sung phần CB còn thiếu bằng popularity (đã mask).
- **So sánh công bằng:** cả 3 model dùng cùng 100k eval user, cùng split theo thời gian, cùng mask (mọi tương tác
  trước thời điểm target) và cùng catalog. Model được chọn trên validation; test chỉ chạy một lần.
