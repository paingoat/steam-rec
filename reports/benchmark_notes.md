
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
