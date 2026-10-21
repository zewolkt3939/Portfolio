# Hướng dẫn sử dụng và vận hành Portfolio CMS

Tài liệu này áp dụng cho website production:

- Website: `https://truongbao.id.vn`
- CMS: `https://truongbao.id.vn/admin/login`
- Analytics: `https://analytics.truongbao.id.vn`
- Thư mục triển khai trên Lightsail: `/srv/portfolio`

Không gửi mật khẩu admin, mã TOTP, recovery code, file `.env` hoặc private key
SSH cho người khác. Khi cần hỗ trợ, chỉ gửi thông báo lỗi đã che thông tin nhạy
cảm.

## 1. Trạng thái production ngày 16/09/2026

Các thành phần đang hoạt động:

- `app`, `postgres`, `caddy` và `umami` đều đang chạy.
- `/health/live` và `/health/ready` trả về `200`.
- PostgreSQL healthy; Alembic đang ở migration `0001_initial_cms (head)`.
- Các trang tĩnh Anh–Việt, CSS, JavaScript, font, CV và chứng chỉ đều tải được.
- HTTPS hợp lệ và Caddy tự gia hạn chứng chỉ Let's Encrypt.
- Host chỉ mở cổng `22`, `80` và `443`; các cổng `3000`, `5432`, `8000`
  chỉ tồn tại trong Docker network.
- SSH chỉ cho phép public key; password và keyboard-interactive authentication
  đã tắt. File `.env` có quyền `600`.
- Umami có một website, và mã tracking đã có trên cả trang tĩnh lẫn Research.
- Có một tài khoản admin đang hoạt động.
- Database có sáu bài đã publish: ba Research và ba Write-up.
- Bộ test mã nguồn đạt 19/19 test.

Các phần chưa hoàn tất:

- `NOTION_API_TOKEN` đang để trống nên chức năng Import Notion chưa sử dụng được.
- `portfolio-backup.timer` chưa được cài/bật. Đây là trạng thái chủ động trong
  giai đoạn bạn chỉ cần website chạy ổn.
- Luồng đăng nhập production, tạo draft, upload và publish chưa được kiểm thử
  thủ công vì cần mật khẩu và TOTP của chủ tài khoản.
- UFW trên Ubuntu đang tắt; cần duy trì rule `22`, `80`, `443` ở Lightsail
  Networking firewall. SSHD hiện cho phép root đăng nhập bằng key
  (`PermitRootLogin without-password`); có thể harden thành `no` sau khi xác
  nhận tài khoản `ubuntu` và `sudo` hoạt động ổn.
- Caddy báo file chưa được format nhưng cấu hình hợp lệ. Umami có một số log
  về Server Reference ID không hợp lệ; UI và tracker vẫn trả `200`, nên theo
  dõi thêm nếu lỗi xuất hiện dày hoặc dashboard hoạt động bất thường.

## 2. Sáu bài Research có sẵn

Sáu bài seed đã được nhập vào production. Lệnh dưới đây là idempotent: chạy lại
sẽ bỏ qua bài không đổi thay vì tạo bản trùng.

```bash
cd /srv/portfolio
docker compose exec app portfolio-cms seed-legacy
```

Kết quả lần đầu dự kiến:

```text
Legacy migration complete: 6 created, 0 updated, 0 unchanged.
```

Kiểm tra:

```bash
curl -s https://truongbao.id.vn/api/v1/posts
```

Mở hai trang:

- `https://truongbao.id.vn/research.html`
- `https://truongbao.id.vn/vi/research.html`

## 3. Đăng nhập CMS

1. Mở `https://truongbao.id.vn/admin/login`.
2. Nhập username và mật khẩu đã tạo bằng lệnh `create-admin`.
3. Nhập mã TOTP sáu số trong ứng dụng Authenticator.
4. Nếu mất thiết bị TOTP, dùng một recovery code. Mỗi code chỉ dùng được một
   lần.

Hệ thống giới hạn năm lần đăng nhập sai trong 15 phút. Nếu bị khóa tạm thời,
không thử liên tục; đợi đủ 15 phút rồi đăng nhập lại.

Sau khi đăng nhập, `/admin/posts` hiển thị danh sách bài. Có thể tìm theo tiêu
đề hoặc slug và lọc theo `draft`, `published`, `archived`.

## 4. Viết một bài mới

Chọn **Bài mới** và điền các trường:

- **Slug:** đường dẫn cố định của bài, chỉ gồm chữ thường ASCII, số và dấu gạch
  ngang. Ví dụ: `htb-lame-writeup`. Không nên đổi slug sau khi đã publish.
- **Loại:** `Research` cho bài nghiên cứu; `Write-up` cho lab hoặc machine.
- **Tiêu đề Việt:** tiêu đề hiển thị chính. Tên machine, project, công cụ và
  chứng chỉ giữ nguyên tiếng Anh.
- **English title:** tiêu đề tiếng Anh, có thể để trống.
- **Tóm tắt Việt:** mô tả ngắn dùng trong danh sách bài.
- **English abstract:** abstract tiếng Anh; trường này bắt buộc.
- **Platform:** ví dụ `Hack The Box`, `PortSwigger Web Security Academy`.
- **Machine / lab:** tên machine hoặc lab.
- **Difficulty:** ví dụ `Easy`, `Medium`, `Hard`.
- **Bằng chứng:** chọn `Personal lab evidence` khi có bằng chứng tự thực hành;
  chọn `Reference walkthrough` khi bài dựa trên tài liệu tham khảo.
- **Tags:** phân cách bằng dấu phẩy, ví dụ `HTB, Web Security, SQL Injection`.
- **Cover URL:** thường để trống; hệ thống tạo Open Graph image khi publish.

Nội dung chính viết bằng Markdown tiếng Việt, dùng đại từ **mình**. Raw HTML bị
vô hiệu hóa để giảm nguy cơ stored XSS.

Cấu trúc gợi ý cho write-up:

```markdown
## Mục tiêu và phạm vi

## Môi trường lab

## Attack path

## Phân tích kỹ thuật

## Bằng chứng

## Remediation

## Retest

## Nguồn tham khảo
```

## 5. Lưu, preview và publish

- Nút **Lưu draft** tạo hoặc cập nhật bản nháp.
- Editor tự lưu sau mỗi 30 giây khi có thay đổi.
- Khung Preview cập nhật sau khi dừng gõ khoảng 350 ms.
- **Full preview** mở bản xem trước hoàn chỉnh; draft không truy cập được từ
  website công khai.
- Khi sửa một bài đã publish, bản public cũ vẫn giữ nguyên cho đến khi bấm
  **Publish** lại.

Trước khi publish write-up, xác nhận cả ba mục:

1. Machine đã retired hoặc nội dung được phép công khai.
2. Đã xóa flag, credential, IP và dữ liệu nhạy cảm.
3. Đã có nguồn, phạm vi, remediation và retest.

URL sau khi publish:

```text
https://truongbao.id.vn/research/<slug>.html
https://truongbao.id.vn/vi/research/<slug>.html
```

Bài mới cũng xuất hiện trong API, sitemap và RSS:

```text
https://truongbao.id.vn/api/v1/posts
https://truongbao.id.vn/sitemap.xml
https://truongbao.id.vn/feed.xml
https://truongbao.id.vn/vi/feed.xml
```

## 6. Chèn ảnh

Trong editor, chọn **Chèn ảnh**:

1. Chọn JPEG, PNG hoặc WebP tối đa 8 MB.
2. Nhập alt text tiếng Việt mô tả nội dung ảnh.
3. CMS kiểm tra nội dung thật, re-encode ảnh, xóa EXIF và đổi tên file.
4. Markdown của ảnh được chèn tại vị trí con trỏ.

Nên dùng ảnh chụp từ lab cá nhân và che username, token, IP, flag hoặc thông tin
không được phép công khai trước khi upload.

## 7. Revision và archive

Mỗi lần lưu hoặc publish tạo một revision. Trong phần **Lịch sử phiên bản**:

- **Xem** mở snapshot cũ.
- **Khôi phục** đưa snapshot vào editor.
- Khôi phục không thay đổi bài public ngay; cần kiểm tra và publish lại.

Nút **Archive** gỡ bài khỏi website, API, sitemap và RSS nhưng giữ dữ liệu cùng
lịch sử. CMS không cung cấp nút xóa vĩnh viễn.

## 8. Import từ Notion

Chức năng này chưa hoạt động cho đến khi cấu hình `NOTION_API_TOKEN`.

Quy trình:

1. Tạo Notion internal integration với quyền đọc.
2. Share đúng page cần nhập cho integration đó.
3. Trên Lightsail, đặt token vào `/srv/portfolio/.env`:

   ```env
   NOTION_API_TOKEN=secret_xxx
   ```

4. Recreate app:

   ```bash
   cd /srv/portfolio
   docker compose up -d --force-recreate app
   ```

5. Trong CMS chọn **Import Notion**, dán URL page rồi chọn **Nhập bản nháp**.

Import luôn tạo/cập nhật draft. Ảnh file của Notion được tải về volume upload;
block không hỗ trợ hoặc ảnh external sẽ được ghi cảnh báo để xử lý thủ công.

## 9. Xem Umami Analytics

Mở `https://analytics.truongbao.id.vn`, đăng nhập tài khoản Umami và chọn website
`truongbao.id.vn`. Các chỉ số hữu ích:

- Page views và visitors.
- Trang Research hoặc Project được xem nhiều.
- Referrer đưa người xem tới portfolio.
- Quốc gia và thiết bị ở mức tổng hợp.

Không bật public share cho dashboard. Sau khi truy cập website bằng trình duyệt,
đợi khoảng một phút rồi kiểm tra realtime để xác nhận tracking.

## 10. Các lệnh vận hành thường dùng

Kiểm tra container:

```bash
cd /srv/portfolio
docker compose ps
```

Kiểm tra ứng dụng và database:

```bash
curl --fail https://truongbao.id.vn/health/live
curl --fail https://truongbao.id.vn/health/ready
```

Xem log gần nhất:

```bash
docker compose logs --tail=100 app caddy postgres umami
```

Theo dõi log trực tiếp, dừng bằng `Ctrl+C`:

```bash
docker compose logs -f --tail=50 app caddy
```

Khởi động lại riêng ứng dụng:

```bash
docker compose restart app
```

Khởi động lại toàn bộ stack:

```bash
docker compose up -d
```

Kiểm tra tài nguyên:

```bash
docker stats --no-stream
free -h
df -h /
```

## 11. Xử lý lỗi nhanh

### Website trả 502

```bash
cd /srv/portfolio
docker compose ps
docker compose logs --tail=150 app caddy postgres
curl -i http://127.0.0.1
```

### `/health/ready` lỗi nhưng `/health/live` còn chạy

Đây thường là lỗi kết nối PostgreSQL:

```bash
docker compose ps postgres
docker compose logs --tail=150 postgres app
```

### Bài không xuất hiện ngoài public

Kiểm tra bài đã ở trạng thái `published`, sau đó:

```bash
curl -s https://truongbao.id.vn/api/v1/posts
```

Nếu vừa sửa bài đã publish, cần bấm **Publish** lại; lưu draft chưa cập nhật bản
public.

### Analytics không có dữ liệu

```bash
grep '^ANALYTICS_' .env
curl -I https://analytics.truongbao.id.vn/script.js
curl -s https://truongbao.id.vn | grep data-website-id
```

Không đăng nội dung `.env` lên issue, chat hoặc repository.

## 12. Backup khi cần bật sau này

Hiện backup timer đang tắt. Khi đã cấu hình xong S3/Restic và muốn bật backup:

```bash
cd /srv/portfolio
docker compose --profile maintenance run --rm backup
docker compose --profile maintenance run --rm \
  --entrypoint portfolio-restore-check backup
```

Chỉ bật timer sau khi cả backup và restore check đều chạy thành công.
