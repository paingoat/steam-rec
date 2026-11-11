# Benchmark — Steam Recommendation MVP

Spark `local[*]` trên **một máy** (đa nhân, không phải cluster). Thời gian là wall-clock của từng stage.

## Quy mô và thời gian

| run | nơi chạy | scale | users | items | train interactions | eval users | silver (s) | gold (s) | train (s) | evaluate (s) | recommend (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `20261111T023229Z-8c56833-dirty-bcadc979` | local | smoke | 7,061 | 1,912 | 31,991 | 5,000 | 99.8 | 7.1 | 20.0 | 3.7 | 6.7 |
| `20261111T023559Z-7b0b390-33e337bc` | local | dev | 78,680 | 7,439 | 393,481 | 20,000 | 113.2 | 19.5 | 135.8 | 19.7 | 8.0 |

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
