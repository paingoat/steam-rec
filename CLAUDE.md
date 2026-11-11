# Steam Recommendation — hướng dẫn cho Claude Code

Bối cảnh dự án: xem `.claude/context/` (gitignored) (propose, plan). Local Ubuntu là source of truth cho code,
dữ liệu cuối cùng, cấu hình và demo; Google Colab chỉ là compute tạm thời.

## Google Colab CLI

- CLI: `colab` (PyPI `google-colab-cli`, cài bằng `uv tool install google-colab-cli`; nâng cấp `uv tool upgrade google-colab-cli`).
  Nguồn: https://github.com/googlecolab/google-colab-cli
- Skill: `.claude/skills/colab-operator/SKILL.md` — bản chính thức, lấy từ `colab skill` của CLI v0.7.5
  (khớp với bản đã cài). Không sửa file này; quy tắc riêng của dự án ghi ở đây. Khi nâng cấp CLI,
  cập nhật bằng `colab skill > .claude/skills/colab-operator/SKILL.md`.
- Auth: ở v0.7.5 mặc định là `--auth=oauth2` (README/skill nói `adc`, nhưng `colab --help` của bản cài là `oauth2`).
  Token được cache tại `~/.config/colab-cli/token.json`, nằm ngoài repo. Kiểm tra bằng `colab whoami` / `colab sessions`.
  Lần đăng nhập đầu là flow copy-paste mã trong trình duyệt, nên người dùng phải tự làm; agent không chạy được.
- Không bao giờ lưu credentials vào repo: không có token, `kaggle.json`, `.env`, service-account JSON, và không nhúng PAT
  vào notebook/script. `colab auth` và `colab drivemount` là thao tác tương tác, nên **để người dùng tự chạy**.

### Quy tắc vận hành (bắt buộc)

1. **Hỏi trước khi tiêu Compute Units.** Phải có đồng ý của người dùng trước khi: tạo VM GPU/TPU, dùng `--high-mem`,
   chạy full pipeline/training, hoặc job dài hơn vài phút. Các lệnh read-only (`sessions`, `status`, `usage`, `ls`, `log`,
   `whoami`, `version`) thì được chạy tự do.
2. **Ưu tiên CPU cho ETL Spark.** Spark `local[*]` trên VM CPU (thêm `--high-mem` khi cần RAM và đã được đồng ý).
   Chỉ dùng GPU khi workload thực sự dùng được GPU (ví dụ embedding/neural model); Spark MLlib ALS/TF-IDF không cần GPU.
   Khi đã cần GPU thì bắt đầu từ `T4`.
3. **Chạy foreground, không chạy detached.** Không dùng `nohup ... &`, `subprocess.Popen` tách rời, `tmux`/`screen`
   để chạy batch job trên VM. Khi kernel idle, VM bị thu hồi (đã từng mất kết quả trong vòng 30 phút).
   Dùng: `colab exec -s NAME --timeout 5400 -f script.py`, hoặc `colab run --timeout ... script.py` cho job ephemeral.
4. **Luôn đặt `--timeout`.** Mặc định của `colab exec`/`colab run` chỉ là **30 giây**. Đặt timeout theo thời gian ước tính
   cộng thêm biên an toàn (smoke: 120–300 s; ETL: 1800–5400 s). Job dài hơn ~90 phút thì chia thành các phase có
   checkpoint, mỗi phase một lệnh `exec`. Với Bash tool local, đặt `timeout`/`run_in_background` phù hợp để lệnh
   `colab exec` không bị cắt giữa chừng.
5. **Tránh truyền dữ liệu.** Dataset Kaggle tải thẳng trên VM (hoặc đọc từ Drive), không upload từ local.
   Chỉ trả về những gì cần: lọc cột/trường thừa trước khi đóng gói (ví dụ: bỏ hidden states `h` khi chỉ cần
   `ids/order/ll` đã giảm bundle từ 470 MB còn 11 MB). Ưu tiên Parquet nén, top-K, metrics, manifest
   thay vì intermediate thô.
6. **Upload file lớn theo chunk.** Một lần upload ~500 MB qua `colab upload` từng lỗi HTTP 500.
   Với file > ~100 MB: ưu tiên dữ liệu đã nằm trên Drive; nếu bắt buộc upload thì `split -b 45M`, upload từng phần
   (~3 phút/phần), ghép lại trên VM và kiểm tra SHA-256.
7. **Checkpoint/artifacts lên persistent storage.** `/content` sẽ mất khi VM dừng. Mỗi phase ghi output + manifest (SHA-256,
   run_id, git commit, config hash) lên Drive (ví dụ `/content/drive/MyDrive/Research/steam-rec/<run_id>/...`) hoặc
   `colab download` về local ngay sau phase. Job phải resume được từ checkpoint, không chạy lại từ đầu.
8. **Quản lý session và dừng VM.** Luôn dùng `-s <tên>` rõ ràng. Trước khi tạo VM mới, kiểm tra `colab sessions`,
   không tạo trùng. Sau khi xong (kể cả khi lỗi), lấy artifacts rồi `colab stop -s <tên>` và xác nhận lại bằng
   `colab sessions`. Ưu tiên `colab run` (tự teardown) cho job một lần.
9. **Báo cáo trung thực.** Nếu lệnh lỗi, timeout hoặc session bị prune thì báo đúng như vậy, kèm `colab log -s NAME -n 20`.
   Không suy đoán là job đã thành công.
10. **Kinh nghiệm từ run full 2026-11-11:**
    - Từ Bash tool, `colab exec` **phải có `< /dev/null`**. Nếu không, client chờ stdin và treo vô hạn, job không bao giờ
      đến kernel.
    - Sau `colab restart-kernel`, hoặc khi session Claude Code kết thúc, phải dừng mọi client `colab exec` cũ ở local
      (TaskStop hoặc `kill <PID>`, **không dùng `pkill -f`** vì nó kill luôn shell hiện tại). Client mồ côi có thể ghi đè log.
    - ALS full (17M tương tác, 3.3M user) trên VM 8 nhân mất khoảng 22 phút mỗi lần fit, kể cả ở rank 32.
      Mỗi lần `exec` chỉ fit một cấu hình (`STEAM_REC_MAX_ALS_FITS=1`, stage train resume được).
