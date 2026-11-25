# EDA — chọn mốc cho split theo thời gian chung (v2)

Nguồn: Bronze Kaggle v28 (đã kiểm SHA-256), chạy `steam-rec eda-time` trên Colab CPU high-mem (khoảng 11 phút) ngày 2026-11-25.
Số liệu đầy đủ ở `reports/eda/eda_time_split.json`. Dữ liệu kết thúc ngày **2022-12-31**.

Quy tắc chia đang xét: train = positive `< T_val` → k-core 3/5 **chỉ trên train**. val = `[T_val, T_test)`, test = `≥ T_test`.
Target là các positive trong cửa sổ, của user **và** item thuộc train-core.

## 1. Lượng review theo tháng (2021-07 → 2022-12)
| tháng | reviews | positives | users |
|---|---|---|---|
| 2021-09 / 10 | 648k / 662k | 553k / 570k | 531k / 543k |
| **2021-11** | **1,185k** | **1,043k** | **1,008k** |
| 2021-12 | 847k | 722k | 679k |
| 2022-01 … 2022-06 | 653k – 875k | 533k – 764k | 532k – 691k |
| 2022-07 / 08 | 808k / 716k | 685k / 616k | 640k / 577k |
| 2022-09 / 10 | 669k / 729k | 558k / 585k | 545k / 597k |
| **2022-11** | **1,282k** | **1,133k** | **1,094k** |
| 2022-12 | 1,003k | 836k | 796k |

Tháng 11 có lượng review **gấp khoảng 1.8–1.9 lần** tháng thường, và lặp lại ở **cả 2021 lẫn 2022** (đợt Autumn Sale cuối
tháng 11). Tháng 12 cũng cao (Winter Sale). Đây là đỉnh theo mùa nên model học được: train đã chứa mùa sale 2021.

## 2. So sánh 4 cặp mốc ứng viên
| | **A** 07-01 / 10-01 | **B** 09-01 / 11-01 | **C** 10-01 / 11-15 | **D** 11-01 / 12-01 |
|---|---|---|---|---|
| Độ dài val / test (ngày) | 92 / 92 | 61 / 61 | 45 / 47 | 30 / 31 |
| Positive train (sau k-core) | 30.9M (20.4M) | 32.2M (21.4M) | 32.7M (21.8M) | 33.3M (22.2M) |
| User / item train-core | 2.88M / 29.7k | 3.00M / 30.7k | 3.05M / 31.2k | 3.11M / 31.7k |
| **val**: user có target | 370k | 259k | 212k | 358k |
| val: target/user (TB) | 1.73 | 1.55 | 1.47 | 1.24 |
| val: % target là item lạnh | 17.3% | 19.3% | 18.0% | 8.7% |
| val rơi vào mùa sale? | không | **không** | không | **có (tháng 11)** |
| **test**: user có target | 443k | 411k | 396k | 195k |
| test: target/user (TB) | 1.58 | 1.45 | 1.39 | 1.43 |
| test: % target là item lạnh | 28.4% | 23.8% | 19.7% | 17.2% |
| test: % review trên game ra mắt trong cửa sổ | 20.3% | 12.3% | 11.0% | 12.2% |
| Khoảng cách từ cuối train tới đầu test | 3 tháng | 2 tháng | 1.5 tháng | 1 tháng |

Ghi chú:
- Mọi phương án đều có **≥ 195k user** cho mỗi split, trong khi eval chỉ lấy mẫu 100k user. Vì vậy cỡ mẫu không phải yếu tố quyết định.
- Model **fit một lần trên train** (đã chốt), nên khoảng cách từ cuối train tới đầu test càng lớn thì model càng "cũ" khi test.
- "% item lạnh" là phần target bị loại vì game không có trong train-core (thường là game mới). CF không gợi ý được những
  game này. Con số này được báo cáo riêng, không tính vào metric.

## 3. Đề xuất: **B — T_val = 2022-09-01, T_test = 2022-11-01**
- **Val tháng 9–10 là giai đoạn lưu lượng bình thường**, phù hợp để chọn hyper-param mà không bị mùa sale làm lệch.
  D có val rơi đúng đỉnh tháng 11, nên đã bị loại.
- **Test tháng 11–12 (61 ngày, 411k user)** bao trọn mùa sale. Đây là kịch bản thực tế quan trọng nhất của Steam, và train đã có
  mùa sale 2021 để học.
- Cân bằng giữa lượng train (21.4M positive sau k-core, 3.0M user) và độ "cũ" của model (2 tháng). A cắt train sớm
  3 tháng nên tỷ lệ item lạnh ở test lên tới 28%.
- Phương án thay thế: **C (10-01 / 11-15)** nếu muốn model ít cũ hơn, đổi lại test bắt đầu giữa tháng 11 và trộn ngày thường
  với ngày sale, còn val ngắn hơn (45 ngày).
