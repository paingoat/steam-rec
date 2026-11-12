# Hướng đi tiếp theo: Kaggle v28 hay thu thập lại bằng Steam Web API?

Ngày 2026-11-12. Tài liệu này dựa trên code và kết quả đang có trong repo (`reports/eda.md`, `reports/benchmark.md`,
`src/steam_rec/**`), cùng với tìm hiểu về Steam Web API và các công trình recommendation liên quan.
Lưu ý về nguồn: session này không truy cập được `steamcommunity.com`, `partner.steamgames.com`, `kaggle.com` và
`arxiv.org`. Vì vậy các chi tiết về API và paper lấy từ kết quả tìm kiếm và nguồn thứ cấp. Mục 7 ghi rõ những điểm
cần tự kiểm tra lại trên trang gốc.

## TL;DR

1. **Tiếp tục dùng Kaggle v28 làm bộ dữ liệu chính. Không chuyển hẳn sang crawl lại từ Steam Web API.**
   Kết quả hiện tại bị giới hạn bởi model và protocol nhiều hơn là bởi dữ liệu. ALS mới thử 2 cấu hình, chưa có các
   baseline mạnh mà paper bắt buộc phải có, và test đang không dùng item validation làm lịch sử.
   Kaggle v28 lớn (41M review, 14M user), công khai, ai cũng tái lập được. Một bộ crawl tự làm thì không đạt được
   quy mô đó ở phía user, vì quota là 100k call/ngày. Bộ đó cũng không chia sẻ lại công khai được.
2. **Steam Web API cho phép đọc dữ liệu của người chơi khác, nhưng chỉ khi profile và "Game details" đang để public.**
   Điều khoản API không nói rõ việc dùng cho nghiên cứu hay công bố dataset. Dữ liệu này cũng là dữ liệu cá nhân
   (pseudonymous). Nếu làm thì giữ ở quy mô nhỏ, cho mục đích học thuật, đã pseudonymize, không công bố dữ liệu thô
   theo từng user.
3. **API nên dùng để bổ sung cho Kaggle, theo thứ tự ưu tiên:**
   (a) metadata **item**: join được qua `app_id`, không có vấn đề quyền riêng tư, sửa được điểm yếu của CB;
   (b) review **2023–2026** từ endpoint review mới: có `playtime_at_review`, text, `refunded`…;
   (c) tùy chọn, một **pilot nhỏ về thư viện game** (owned games + playtime + friends), chụp 2 snapshot cách nhau vài tuần.
   Lưu ý `user_id` trong Kaggle đã ẩn danh, nên **không thể** dùng API để làm giàu thêm cho user của Kaggle.

---

## 1. Kết quả hiện tại đứng ở đâu so với paper

### 1.1 Không so sánh trực tiếp con số giữa các dataset hoặc protocol khác nhau
| dataset | users | items | interactions | TB/user | density | so với Kaggle-core |
|---|---|---|---|---|---|---|
| MovieLens-1M | 6,040 | 3,706 | 1.0M | ~166 | 4.5% | dày hơn ~200 lần |
| MovieLens-20M | 138,493 | 26,744 | 20.0M | ~144 | 0.54% | dày hơn ~25 lần |
| Steam (bản SASRec/BERT4Rec, review 2010–2018) | 281,428 | 13,044 | 3.49M | 12.4 | 0.095% | dày hơn ~4 lần |
| **Kaggle v28, k-core 3/5 (repo này)** | **3.30M** | **32,692** | **23.7M** | **7.2 (train: 5.2)** | **0.022%** | — |

Dữ liệu của repo thưa hơn rất nhiều. Lịch sử của mỗi user cũng rất ngắn, trung bình chỉ 5.2 positive trong train.
Số candidate thì lớn hơn bản Steam học thuật khoảng 2.5 lần. Ba yếu tố này đều kéo Recall/NDCG tuyệt đối xuống.
Vì vậy, "MovieLens có Recall@20 cao hơn nhiều" không có nghĩa là model của mình kém. Ví dụ, trên ML-20M với protocol
*strong generalization*, Mult-VAE và EASE đạt Recall@20 khoảng 0.39. Đó là protocol khác hẳn: user mới, 20% item
của user làm target, dữ liệu dày.

### 1.2 Những gì so sánh được
- **Mức cải thiện so với popularity trên cùng protocol:** ALS / popularity = **1.72× (Recall@20)** và **1.90× (NDCG@20)**.
  Đây là mức hợp lý cho MF trên dữ liệu implicit thưa. Không có dấu hiệu bất thường, nhưng cũng chưa có gì nổi bật.
- **So với sequential model trên Steam:** protocol của repo đã là leave-last-out + full ranking, giống chuẩn SASRec/BERT4Rec
  sau khi cộng đồng bỏ sampled metrics (Krichene & Rendle, KDD 2020). Các trích dẫn thứ cấp cho thấy SASRec/BERT4Rec
  trên Steam (bản 281k user) đạt NDCG@10 full-ranking khoảng **0.05–0.08**. ALS của repo đạt **0.036** trên một bộ
  thưa hơn, có nhiều candidate hơn, và test lại không dùng item val làm lịch sử. Mức này phù hợp với một baseline
  không tuần tự. Còn chỗ để cải thiện rõ ràng, nhưng nằm ở phía model.
- **Chuẩn của cộng đồng:** Dacrema et al. (RecSys 2019) và Rendle et al. (RecSys 2021/2022) cho thấy ItemKNN, EASE
  và iALS được tune kỹ thường ngang hoặc hơn model neural. Một paper hoặc project nghiêm túc cần có các baseline này.
  Repo hiện mới có popularity, ALS (2 cấu hình, rank 32, chỉ thử một regParam) và CB TF-IDF.

### 1.3 Các vấn đề phương pháp tìm thấy trong code (nên sửa trước khi đổi dữ liệu)
1. **Test không đưa item val vào lịch sử.** `user_inputs(..., "test")` chỉ lấy `split='train'` làm `hist`, và ALS chỉ fit
   trên train (`scoring.py`, `modeling.run_evaluate`). Nghĩa là test đang dự đoán item cách 2 bước so với lịch sử.
   Paper Steam/SASRec thì đưa item val vào chuỗi đầu vào khi test. Đây là một nguyên nhân khiến ALS giảm từ val sang
   test (Recall@20 0.142 → 0.109; popularity 0.080 → 0.063). Phần còn lại có thể do drift theo thời gian.
   **Sửa:** sau khi chọn cấu hình trên val, refit trên train+val (hoặc fold-in user factor), và nối thêm item val
   vào `hist` cho CB/kNN.
2. **K-core tính trên toàn bộ positive trước khi split** (`gold.py`). Trong khi đó `docs/data-contracts.md` ghi là "k-core
   chỉ tính trên train". Cách hiện tại phổ biến trong paper, nhưng cần sửa cho code và tài liệu khớp nhau.
   Có thể chuyển k-core sang chỉ tính trên train, hoặc ghi rõ đây là ngoại lệ.
3. **Target nguội bị bỏ khỏi eval mà không báo cáo.** `gold.eval_users` có ghi `eval_candidates` và `warm_candidates`, nhưng
   `benchmark.md` không hiển thị. Game mới ra là một phần lớn của review cuối cùng, nên tỉ lệ bị loại này cần được nêu rõ.
4. **Ý nghĩa của `hours` chưa rõ.** Rất có thể đây là playtime tại thời điểm crawl, không phải lúc review. Khi đó
   confidence của interaction trong train chứa thông tin từ tương lai. Mức độ nhẹ, nhưng nên ghi chú lại.
   Endpoint review mới có `playtime_at_review`, giải quyết được điểm này (mục 4).

## 2. EDA Kaggle v28: những gì quyết định hướng đi
Lấy từ `reports/eda.md` và `reports/eda/eda_summary.json`, có tính thêm một số số liệu suy ra:

- **Review chỉ là một lát mỏng của hành vi.** Mỗi user có median 1 review, p90 = 6. 92% user có dưới 3 positive, nên chỉ
  khoảng 24% user (3.30M) vào được eval. `users.products` (số game sở hữu) **chưa được phân tích**. Tỉ lệ
  `reviews / products` sẽ cho thấy review che phủ bao nhiêu phần thư viện. Đây chính là luận điểm chính để cân nhắc
  thu thập owned games (mục 4c).
- **Negative hiếm:** 85.8% review là positive. Repo đang dùng negative để mask là đúng. Không nên kỳ vọng nhiều vào
  việc học trực tiếp từ negative.
- **Drift theo thời gian mạnh:** 2020–2022 chiếm 63% số review, tỉ lệ positive theo năm dao động 0.81–0.97. Review cuối
  cùng (target test) thường thuộc giai đoạn mới nhất. Vì vậy cần thêm baseline **popularity theo thời gian**
  (config đã có sẵn `recent_days`), và cần đo tỉ lệ target là game mới ra (ví dụ phát hành trong vòng 90 ngày
  trước ngày review).
- **Đuôi dài và popularity bias:** median 28 positive mỗi game, max 295k. ALS chỉ phủ 2.5% catalog (khoảng 800 game
  trong top-20). Nên báo cáo thêm metric theo nhóm độ phổ biến của item (head/torso/tail), novelty và coverage.
- **Metadata hỏng ở đúng nhóm game quan trọng:** 20% game có description rỗng, và **nhiều game phổ biến nhất (TF2, Witcher 3,
  CS:GO, Destiny 2…) không có tag lẫn description**. CB thua chủ yếu vì dữ liệu, không phải vì thuật toán.
  Bổ sung bằng API sửa được trực tiếp điểm này.
- **Dữ liệu đã cũ:** dừng ở 2022-12-31. Không có game hay review nào từ 2023–2026.
- **`user_id` đã ẩn danh:** giá trị kiểu `11442391`, không phải SteamID64 dạng `7656119…`. Vì vậy không join được user
  Kaggle với Steam API. Chỉ join được theo `app_id`.

**EDA nên bổ sung**, chạy được ngay trên Bronze, không cần dữ liệu mới:
(1) phân phối `products` và `reviews/products`;
(2) tỉ lệ target test/val là game phát hành gần ngày review, và tỉ lệ target bị loại vì nguội;
(3) Recall của popularity tính theo cửa sổ thời gian (7/30/90 ngày trước target);
(4) độ phổ biến của target test so với item trong train;
(5) độ dài lịch sử theo năm tham gia của user.

## 3. Steam Web API có cho thu thập dữ liệu người chơi khác không?

**Về kỹ thuật thì có.** `IPlayerService/GetOwnedGames`, `ISteamUser/GetFriendList` và `GetPlayerSummaries` nhận bất kỳ
SteamID nào, không cần OAuth của chủ tài khoản. Dữ liệu chỉ được trả về khi người đó để public:
- Từ cập nhật quyền riêng tư ngày 2018-04-10/11, **"Game details"** (thư viện, playtime, wishlist, achievement) là một
  thiết lập riêng, mặc định không public. Hệ quả là SteamSpy kiểu cũ ngừng hoạt động. Profile public chưa đủ, mà
  "Game details" cũng phải public. Một mẫu không học thuật cho thấy khoảng 1/10 tài khoản đọc được thư viện. Con số
  này nên đo lại bằng pilot.
- Profile private hoặc game details private thì `GetOwnedGames` trả về `{"response":{}}`. Response rỗng đôi khi chỉ là
  lỗi tạm thời, nên cần retry trước khi kết luận là private.

**Về điều khoản (Steam Web API Terms of Use):**
- License có giới hạn, không độc quyền, gắn với ứng dụng của bạn. Được phân phối "Steam Data" cho end user dùng cá nhân
  qua ứng dụng đó. Giới hạn **100,000 call/ngày** cho mỗi key. Không được vi phạm Steam Subscriber Agreement, không dùng
  để gửi marketing không được yêu cầu. Valve có thể đổi điều khoản hoặc thu hồi quyền truy cập bất cứ lúc nào.
- Điều khoản **không có điều nào về nghiên cứu hay công bố dataset.** Công bố công khai dữ liệu thô theo user, kèm
  SteamID, nhiều khả năng vượt quá phạm vi "personal use" của license.
- Đã có tiền lệ học thuật: O'Neill et al. (IMC 2016) crawl khoảng 108M tài khoản qua Web API; UCSD/McAuley công bố
  bộ Steam có `steam_id`, owned items và playtime. Nhưng tiền lệ không thay cho sự cho phép.

**Về pháp lý dữ liệu cá nhân:** SteamID kèm thư viện, playtime và danh sách bạn bè là dữ liệu cá nhân dạng pseudonymous.
GDPR áp dụng với user ở EU. Ở Việt Nam, **Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15** có hiệu lực từ 2026-01-01
(cùng Nghị định 356/2025), thay Nghị định 13/2023. Luật này không loại dữ liệu "đã công khai" ra khỏi phạm vi điều chỉnh.

**Kết luận thực tế:** với project học thuật, có thể crawl dữ liệu public nếu tuân thủ các điều sau:
1. Chỉ gọi API chính thức, tôn trọng quota và retry/backoff. Không scrape HTML profile, không tìm cách vượt qua profile private.
2. **Tối thiểu hóa dữ liệu:** không lưu `personaname`, avatar, `profileurl`, `realname`, `loccountrycode`.
3. **Pseudonymize ngay khi ghi Bronze:** HMAC-SHA256(steamid, salt bí mật). Salt nằm trong `.env`, không commit.
   SteamID gốc chỉ nằm trong danh sách crawl frontier, đặt ngoài lake và xóa sau khi crawl xong snapshot cuối.
4. Không công bố dữ liệu theo từng user. Chỉ công bố code, metric, model và số liệu tổng hợp.
5. Nếu đây là nghiên cứu chính thức (luận văn, paper), hỏi giảng viên hoặc hội đồng đạo đức, và ghi rõ trong báo cáo.

## 4. Nếu dùng API thì nên thu thập gì để hơn Kaggle

Thứ tự ưu tiên tính theo lợi ích chia cho rủi ro và chi phí:

### (a) Item: ưu tiên cao nhất, rủi ro gần như bằng 0, join được với Kaggle qua `app_id`
| nguồn | trường cần lấy | giải quyết vấn đề gì |
|---|---|---|
| Store `appdetails` (khoảng 200 request / 5 phút / IP, không chính thức) | type, `release_date`, `is_free`, price, **genres**, **categories** (single/multi/co-op, controller…), developers, publishers, `short_description`, supported languages, platforms, `required_age`, content descriptors, `metacritic`, `recommendations.total`, DLC list | Lấp chỗ thiếu tag/description của game phổ biến. Có feature có cấu trúc cho hybrid hoặc cold-start. Có ngày phát hành để làm popularity theo thời gian. |
| User tags **có số vote** (store/`IStoreBrowseService`/SteamSpy) | tag và trọng số | Tag của Kaggle không có trọng số. Có trọng số thì TF-IDF hoặc embedding của tag tốt hơn. |
| `GetAppReviews` query_summary | tổng positive/negative, review score | Prior về chất lượng cho ranking. |
| `ISteamUserStats/GetGlobalAchievementPercentagesForApp` | % hoàn thành từng achievement | Feature về độ khó và mức gắn bó với game. |

Khoảng 50k app × 1–3 call, mất khoảng 1–2 ngày crawl ở local. Đây là lựa chọn tốt nhất cho CB, hybrid và demo cold-start.

### (b) Review mới 2023–2026: ưu tiên trung bình
Từ **2026-10-22**, endpoint cũ `store.steampowered.com/appreviews/<appid>?json=1` đã bị tắt. Endpoint thay thế là
**`IUserReviewsService/GetAppReviews`**: key không bắt buộc, có key thì được rate limit cao hơn. Endpoint mới
**bỏ `author.num_games_owned`**, thêm `refunded`, và có thêm filter theo ngày, playtime và Steam Deck.
Các trường nên lấy: `recommendationid`, `author.steamid` (lưu dạng HMAC), `voted_up`, `timestamp_created/updated`,
**`playtime_at_review`**, `playtime_forever`, `playtime_last_two_weeks`, `last_played`, `author.num_reviews`, `language`,
`votes_up`, `weighted_vote_score`, `steam_purchase`, `received_for_free`, `written_during_early_access`, **`refunded`**,
`primarily_steam_deck`, và review text (tùy chọn, cho NLP/LLM).

So với Kaggle, bộ này hơn ở các điểm:
- confidence dùng `playtime_at_review`, không bị lẫn thông tin tương lai;
- tín hiệu chơi tiếp sau khi review (`playtime_forever − playtime_at_review`);
- negative mạnh hơn (`refunded`);
- có text;
- có timestamp đến giây, không còn bị trùng thứ tự trong cùng ngày;
- có SteamID thật, nên làm được bước (c).

Kaggle và bộ mới chung `app_id` nhưng không chung user. Vì vậy dùng bộ mới như **một dataset thứ hai**, hoặc làm tập
**test ngoài thời gian** (train ≤ 2022, test 2023+) cho các model phía item như popularity, CB và item-kNN.

### (c) User: chỉ làm pilot nhỏ, có kiểm soát
| endpoint | trường | ghi chú |
|---|---|---|
| `IPlayerService/GetOwnedGames` (`include_played_free_games=1`, `include_appinfo=0`) | appid, `playtime_forever`, `playtime_2weeks`, `rtime_last_played` (cần kiểm tra lại trên response thật) | Toàn bộ thư viện kèm playtime. Dày hơn review rất nhiều. "Có nhưng chưa chơi" cho tín hiệu về exposure. |
| `ISteamUser/GetFriendList` | steamid bạn bè (HMAC), `friend_since` | Đồ thị xã hội cho social rec. Đồng thời là cách mở rộng crawl, nhưng snowball sampling bị lệch về user có nhiều bạn. |
| Wishlist (`IWishlistService/GetWishlist`) | appid, ngày thêm (cần kiểm tra) | Tín hiệu ý định mua, có mốc thời gian. |
| `GetPlayerSummaries` | chỉ `communityvisibilitystate`, `timecreated` | Tuổi tài khoản. Bỏ mọi trường định danh. |

Không nên lấy: achievement theo từng user (mỗi cặp user × game tốn 1 call, quá đắt), inventory, market.

**Thiết kế để có time-aware ground truth:** owned games **không có ngày mua**. Vì vậy cần chụp **2 snapshot cách nhau
3–4 tuần**. Target là game mới xuất hiện trong thư viện, hoặc game có playtime tăng giữa T0 và T1. Không có bước này
thì chỉ làm được random split, kém hơn protocol theo thời gian mà repo đang có.

**Quy mô:** user seed lấy từ tác giả review ở mục (b), vì đây là user có hoạt động thật. 100k user tốn khoảng 1 ngày
quota mỗi endpoint. Nếu chỉ khoảng 10–30% đọc được thư viện, sẽ thu được 10–30k thư viện, khoảng 1–3M interaction
mỗi snapshot. Con số này đủ cho một thí nghiệm "review hay thư viện: tín hiệu nào tốt hơn". Nó **không** đủ để thay Kaggle
(muốn có 14M user thì cần khoảng 140 ngày quota). Cần nêu rõ selection bias: chỉ có user để public và có viết review.

**Chạy ở đâu:** crawler chạy ở local Ubuntu, vì local là source of truth, crawl tốn I/O chứ không tốn CPU, và Colab cấm
chạy detached. Ghi vào `bronze/steam_api/<endpoint>/<snapshot>/` kèm manifest SHA-256, giống Kaggle. API key để trong `.env`.

## 5. Lộ trình đề xuất
| bước | nội dung | dữ liệu | compute |
|---|---|---|---|
| **P0** | Sửa eval: đưa item val vào lịch sử khi test (refit train+val hoặc fold-in); báo cáo target nguội; thống nhất k-core giữa code và tài liệu; thêm metric theo nhóm độ phổ biến và theo nhóm user | Kaggle | local, dev scale |
| **P1** | Baseline mạnh: **popularity theo thời gian** (`recent_days`), **ItemKNN/RP3β**, **EASE** (Gram 32.7k² float32 khoảng 4.3 GB), **iALS tune đúng cách** (rank 64–256, grid regParam, ≥ 15 vòng) bằng thư viện `implicit` (nhanh hơn Spark MLlib nhiều trên một máy) | Kaggle | Colab CPU high-mem, khoảng 0.3–1 CU |
| **P2** | **SASRec/gSASRec** (Steam là dataset chuẩn của dòng model này, protocol của repo đã khớp). Đây là cách so sánh trực tiếp với paper | Kaggle | Colab T4, cần hỏi trước vì tốn CU |
| **P3** | API item enrichment (mục 4a), sau đó CB/hybrid (LightFM hoặc two-tower dùng genres, categories, tag có trọng số) | Kaggle + API item | crawler local |
| **P4** (tùy chọn) | Review 2023–2026 (4b) để test ngoài thời gian. Pilot thư viện game với 2 snapshot (4c) | API | crawler local |

Giữ Spark cho ETL và ALS như kiến trúc big data hiện tại. Phần tune và so sánh model ở một máy nên dùng numpy,
`implicit` hoặc PyTorch để tránh tốn 22 phút cho mỗi lần fit ALS bằng Spark.

## 6. Khi nào nên cân nhắc chuyển hẳn sang API
Chỉ nên chuyển khi mục tiêu của project đổi từ "recommend review tiếp theo" sang "recommend game sẽ chơi hoặc mua tiếp"
(dựa trên thư viện và playtime), **và** chấp nhận được các điều kiện: dataset nhỏ hơn hàng chục lần, có selection bias,
không công bố được dữ liệu, và mất ít nhất 1 tháng để có 2 snapshot. Nếu P0–P2 cho thấy các model mạnh đều bão hòa
trên Kaggle (khoảng cách giữa SASRec, EASE và iALS rất nhỏ) thì giá trị của dữ liệu thư viện mới vượt chi phí. Đến lúc
đó pilot (4c) sẽ cho bằng chứng trước khi đầu tư lớn.

## 7. Cần tự kiểm tra lại trên nguồn gốc
- Toàn văn Steam Web API Terms of Use: https://steamcommunity.com/dev/apiterms
- Tài liệu `IUserReviewsService/GetAppReviews` và phần "Migrating from /appreviews": rate limit, tên trường, `playtime_at_review`.
- Response thật của `GetOwnedGames` (`rtime_last_played`) và wishlist (trường ngày thêm).
- Trang Kaggle của dataset: license, version mới hơn v28 (nếu có), định nghĩa chính xác của `hours`.
- Bảng kết quả full-ranking trên Steam trong các paper SASRec/BERT4Rec/gSASRec. Các con số ở mục 1.2 là trích dẫn thứ cấp.

## Nguồn
- Steam Web API Terms of Use — https://steamcommunity.com/dev/apiterms
- Steam Web API (Valve Developer wiki) — https://developer.valvesoftware.com/wiki/Steam_Web_API
- IPlayerService (Steamworks) — https://partner.steamgames.com/doc/webapi/IPlayerService
- IUserReviewsService (Steamworks) — https://partner.steamgames.com/doc/webapi/IUserReviewsService
- Steam getreviews (tài liệu cũ) — https://partner.steamgames.com/doc/store/getreviews
- Endpoint review công khai tắt ngày 22/10 — https://mixed-news.com/en/?p=35244 · https://gamedev.net/news/6178/
- Thay đổi quyền riêng tư 2018 và SteamSpy — https://www.engadget.com/2018/04/11/steam-new-privacy-features-disable-steam-spy/ ·
  https://gamedeveloper.com/business/steam-privacy-tweaks-spell-the-end-for-services-like-steam-spy ·
  https://en.wikipedia.org/wiki/Steam_Spy
- Lỗi response rỗng của GetOwnedGames — https://developer.valvesoftware.com/wiki/Steam_Web_API/Feedback ·
  https://github.com/lutris/lutris/issues/6890
- Mẫu không học thuật về tỉ lệ thư viện public — https://gamingprofileviewer.com/steam/guides/steam-backlog-statistics
- Rate limit của appdetails — https://steamdb.info/blog/5
- O'Neill et al., "Condensing Steam", IMC 2016 — https://zappala.byu.edu/pubs/steam-imc-2016.pdf
- Bộ dữ liệu Steam của UCSD/McAuley — https://cseweb.ucsd.edu/~jmcauley/datasets.html
- Kang & McAuley, SASRec (ICDM 2018) — https://arxiv.org/pdf/1808.09781
- Sun et al., BERT4Rec (CIKM 2019) — https://arxiv.org/pdf/1904.06690
- Petrov & Macdonald, BERT4Rec replicability (RecSys 2022) — https://arxiv.org/pdf/2207.07483
- Petrov & Macdonald, gSASRec (RecSys 2023) — https://arxiv.org/pdf/2308.07192
- Klenitskiy & Vasilev, "Turning Dross Into Gold Loss" (RecSys 2023) — https://arxiv.org/pdf/2309.07602
- Krichene & Rendle, "On Sampled Metrics for Item Recommendation" (KDD 2020) — https://arxiv.org/pdf/1912.02263
- Rendle et al., "Revisiting the Performance of iALS…" (RecSys 2022) — https://arxiv.org/pdf/2110.14037
- Dacrema et al., "Are We Really Making Much Progress?" (RecSys 2019)
- Luật BVDLCN 91/2025/QH15 — https://vn.rajahtannasia.com/?p=63356 ·
  https://fpf.org/wp-content/uploads/2025/12/FPF-Issue-Brief-Making-Sense-of-Vietnams-Latest-Data-Protection-and-Governance-Regime.pdf
