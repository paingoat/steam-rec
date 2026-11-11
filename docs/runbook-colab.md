# Runbook — Colab CLI (M5/M6)

Áp dụng `CLAUDE.md` (9 quy tắc vận hành) và skill `.claude/skills/colab-operator/`.
Session mặc định: `steam-rec-mvp`. Drive: `/content/drive/MyDrive/Research/steam-rec/<run_id>/`.
👤 = bước người dùng phải tự làm.

## 0. Kiểm tra (read-only, không tốn CU)
```bash
colab whoami && colab sessions && colab usage
```
Nếu gặp 401/403 hoặc token hết hạn: 👤 chạy lại `colab sessions` trong terminal riêng và dán mã đăng nhập.
`colab auth` **không** sửa được lỗi này.

## 1. Tạo VM và mount Drive
```bash
colab new -s steam-rec-mvp --high-mem          # CPU high-RAM (đã duyệt: gói Pro)
```
👤 `colab drivemount -s steam-rec-mvp` (cần thao tác consent trong trình duyệt).

## 2. Đồng bộ code (snapshot theo commit, không cần GitHub/PAT)
```bash
git archive --format=tar.gz HEAD > /tmp/claude-.../src.tgz   # chỉ đóng gói code đã commit
git rev-parse HEAD > src.sha
colab upload -s steam-rec-mvp src.tgz /content/src.tgz
colab upload -s steam-rec-mvp src.sha /content/src.sha
uv run python -c "...get bronze _manifest.json..." > bronze_manifest_local.json   # vài KB
colab upload -s steam-rec-mvp bronze_manifest_local.json /content/bronze_manifest_local.json
colab exec -s steam-rec-mvp --timeout 900 -f scripts/colab/bootstrap.py
```
Kernel giữ module đã import giữa các lần `exec`. **Sau khi upload code mới**, chạy
`colab restart-kernel -s steam-rec-mvp` rồi bootstrap lại.

## 3. Ingest trên VM và đối chiếu Bronze local
```bash
colab exec -s steam-rec-mvp --timeout 1800 --env STAGES=ingest --env SCALE=full -f scripts/colab/run_stage.py
```
kagglehub thử tải ẩn danh trước. Nếu bị chặn, truyền `--env KAGGLE_USERNAME=... --env KAGGLE_KEY=...`
(giá trị có thể nằm lại trong `~/.config/colab-cli/history`, file có quyền 0600).
Nếu SHA-256 khác Bronze local thì stage dừng.

## 4. Pipeline: mỗi lần `exec` là một hoặc vài stage, chạy foreground
```bash
RID=<YYYYMMDDTHHMMSSZ-sha-cfg>   # cố định cho cả lần chạy
colab exec -s steam-rec-mvp --timeout 5400 --env STAGES=silver,gold --env SCALE=full --env RUN_ID=$RID -f scripts/colab/run_stage.py
colab exec -s steam-rec-mvp --timeout 5400 --env STAGES=train      --env SCALE=full --env RUN_ID=$RID -f scripts/colab/run_stage.py
colab exec -s steam-rec-mvp --timeout 3600 --env STAGES=evaluate,recommend,export --env SCALE=full --env RUN_ID=$RID -f scripts/colab/run_stage.py
```
- Phía local, Bash tool dùng `run_in_background: true`, vì giới hạn 10 phút chỉ áp cho tool local.
  Job trên VM vẫn chạy foreground trong kernel. **Không dùng `nohup` hay `&` trên VM.**
- Sau mỗi stage: lake (silver, gold, artifacts của `RID`) được mirror lên Drive.
  Stage đã xong có marker `artifacts/<RID>/stages/<stage>.json`, chạy lại sẽ tự bỏ qua.
- Theo dõi: stdout, `colab status -s steam-rec-mvp`, `colab log -s steam-rec-mvp -n 20`.

## 5. Lấy kết quả về và dừng VM
```bash
colab ls -s steam-rec-mvp /content/export/$RID
for f in ...parts...; do colab download -s steam-rec-mvp /content/export/$RID/$f data/inbox/$RID/$f; done
uv run steam-rec import --bundle-dir data/inbox/$RID      # verify SHA-256 + import vào SILO
colab stop -s steam-rec-mvp && colab sessions             # bắt buộc, kể cả khi lỗi
```
Model Spark ALS đầy đủ (user factors, cỡ GB) chỉ nằm trên Drive. Bundle chỉ chứa phần dùng cho serving:
top-K, metrics, item factors, CB kNN, catalog.

## Recovery
| Triệu chứng | Cách xử lý |
|---|---|
| `Session not found` / 404 / VM bị thu hồi | `colab sessions` → `colab new` → 👤 drivemount → bootstrap → chạy lại `run_stage` với **cùng `RUN_ID`**. Lake được khôi phục từ Drive, stage đã xong sẽ bị bỏ qua |
| Kernel treo | `colab restart-kernel -s steam-rec-mvp`, bootstrap, chạy lại stage |
| `Drive not mounted` | 👤 `colab drivemount -s steam-rec-mvp` |
| OOM Spark | giảm `STEAM_REC_DRIVER_MEMORY`/tăng `STEAM_REC_SHUFFLE_PARTITIONS` qua `--env`, hoặc thu nhỏ grid ALS |
