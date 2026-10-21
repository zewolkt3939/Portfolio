## 1. Mục tiêu của bài thực hành điều tra số (DFIR)

Khi điều tra một sự cố xâm nhập máy chủ web, việc chỉ nhìn vào một nguồn log duy nhất thường dẫn tới kết luận thiếu chính xác: một dòng `POST /upload.php HTTP/1.1" 200` trong `access.log` của Nginx chỉ cho biết yêu cầu tải tệp nhận phản hồi thành công, chưa chứng minh tệp đó đã được thực thi; ngược lại, một dòng `Accepted publickey` trong `/var/log/auth.log` trông hoàn toàn hợp lệ nếu đứng tách biệt khỏi sự kiện tiến trình web vừa ghi thêm khóa SSH hai phút trước đó.

Ghi chép này trình bày quy trình dựng lại **timeline sự cố đa nguồn (multi-source incident timeline)** trên một bộ dữ liệu nhật ký tổng hợp, kết nối bốn lớp dấu vết: **nhật ký truy cập HTTP**, **nhật ký tiến trình con**, **nhật ký xác thực hệ thống** và **dấu vết duy trì quyền truy cập (persistence)**.

[![Sơ đồ timeline sự cố web liên kết bốn nguồn log từ Nginx access.log đến thực thi tiến trình con và duy trì quyền truy cập.](/assets/research/dfir-timeline.svg)](/assets/research/dfir-timeline.svg)

Hình 1. Sơ đồ liên kết bốn mốc thời gian chuẩn hóa UTC giúp nối hành vi tải tệp trên web với phiên đăng nhập SSH và tác vụ cron duy trì quyền truy cập.

## 2. Chuẩn hóa thời gian và định danh thực thể xoay trục (Pivot Entities)

Trước khi lọc bất kỳ dòng log nào, bước bắt buộc trong điều tra là **đưa mọi nguồn nhật ký về cùng múi giờ UTC (ISO 8601)** và xác định các thực thể dùng để xoay trục (pivot):

- **Từ mạng vào ứng dụng:** Địa chỉ IP nguồn (`198.51.100.42`), `User-Agent`, đường dẫn URI và mã trạng thái HTTP.
- **Từ ứng dụng xuống hệ điều hành:** Tài khoản dịch vụ chạy worker (`www-data`), PID tiến trình cha (`php-fpm` / `gunicorn`) và thời điểm sửa đổi tệp (`mtime` / `ctime`).
- **Từ tiến trình con sang xác thực và persistence:** Tài khoản đích trên máy chủ (`deploy`), khóa công khai trong `~/.ssh/authorized_keys` và tệp cấu hình trong `/etc/cron.d/`.

## 3. Phân tích từng chặng trên dữ liệu nhật ký

### Chặng 1 (`08:12:04Z`): Quét dò đường dẫn và tải tệp bất thường trên Nginx

Trong nhật ký truy cập web, một chuỗi phản hồi `404` tốc độ cao từ cùng một IP nguồn theo sau bởi một yêu cầu `POST` trả về `200 OK` và các yêu cầu `GET` tới thư mục chứa tệp người dùng tải lên là điểm neo đầu tiên:

```text
198.51.100.42 - - [15/Sep/2026:08:11:58 +0000] "GET /.env HTTP/1.1" 404 153 "-" "Mozilla/5.0"
198.51.100.42 - - [15/Sep/2026:08:12:01 +0000] "GET /admin/config.php HTTP/1.1" 404 153 "-" "Mozilla/5.0"
198.51.100.42 - - [15/Sep/2026:08:12:04 +0000] "POST /api/import-avatar.php HTTP/1.1" 200 84 "-" "Mozilla/5.0"
198.51.100.42 - - [15/Sep/2026:08:14:18 +0000] "GET /uploads/avatars/theme-check.php?cmd=id HTTP/1.1" 200 112 "-" "curl/8.5.0"
```

Quan sát quan trọng: yêu cầu ở `08:14:18Z` truy cập trực tiếp một tệp `.php` bên trong thư mục `/uploads/avatars/` với `User-Agent` đổi từ trình duyệt sang `curl/8.5.0`.

### Chặng 2 (`08:14:19Z`): Dấu vết khởi tạo shell con từ tiến trình web

Đối chiếu mốc thời gian `08:14:18Z` với nhật ký audit (`auditd` / process accounting), tiến trình worker chạy dưới UID `www-data` đã gọi `/bin/sh -c`:

```text
type=EXECVE msg=audit(1789460059.120:412): argc=3 a0="/bin/sh" a1="-c" a2="id; whoami; ls -la /home/deploy/.ssh"
```

Sự trùng khớp trong khoảng **1 giây** giữa request `GET /uploads/avatars/theme-check.php` và sự kiện `EXECVE` dưới quyền `www-data` xác nhận tệp tải lên đã thực thi mã trên máy chủ (Web Shell execution — [MITRE ATT&CK T1505.003](https://attack.mitre.org/techniques/T1505/003/)).

### Chặng 3 (`08:16:42Z` – `08:18:05Z`): Chuyển dịch sang SSH và tạo persistence

Hai phút sau khi dò thư mục `/home/deploy/.ssh`, nhật ký `/var/log/auth.log` ghi nhận một phiên đăng nhập SSH thành công từ chính IP `198.51.100.42`:

```text
2026-09-15T08:16:42Z web-node-01 sshd[4821]: Accepted publickey for deploy from 198.51.100.42 port 51924 ssh2: ED25519 SHA256:k9x...
2026-09-15T08:18:05Z web-node-01 cron[892]: (*system*) RELOAD (/etc/cron.d/health-sync)
```

Khi kiểm tra siêu dữ liệu tệp trên hệ thống tệp (`stat`), cả `/home/deploy/.ssh/authorized_keys` lẫn `/etc/cron.d/health-sync` đều có `mtime` nằm trong khoảng `08:15:30Z` – `08:18:00Z`. Như vậy, kẻ tấn công đã lợi dụng quyền ghi không đúng chỗ trên thư mục người dùng để chèn khóa SSH, chuyển từ web shell sang phiên tương tác ổn định và cài đặt cron job duy trì kết nối.

## 4. Bảng kiểm tra phạm vi khắc phục (Containment & Eradication Checklist)

Nếu người vận hành chỉ xóa tệp `theme-check.php` trong `/uploads/avatars/`, kẻ tấn công vẫn giữ được quyền truy cập qua khóa SSH và cron job. Việc dựng đầy đủ timeline giúp đảm bảo khâu làm sạch bao phủ mọi dấu vết:

| Giai đoạn trong timeline | Dấu vết phát hiện (Artifact) | Hành động ứng phó và khắc phục |
| --- | --- | --- |
| **Initial Access (`08:12:04Z`)** | `/api/import-avatar.php` cho phép lưu tệp `.php`. | Kiểm tra định dạng tệp phía server, đổi tên tệp ngẫu nhiên và tắt thực thi script (`php_flag engine off` / Nginx `location ~ \.php$` loại trừ `/uploads/`). |
| **Execution (`08:14:19Z`)** | `/uploads/avatars/theme-check.php` chạy dưới `www-data`. | Cách ly tệp mẫu để lưu bằng chứng (hash SHA-256), xóa tệp khỏi thư mục phục vụ web và thu hẹp quyền hệ thống tệp của `www-data`. |
| **Lateral / Credential (`08:16:42Z`)** | Khóa lạ trong `/home/deploy/.ssh/authorized_keys`. | Thu hồi khóa trái phép, chấm dứt phiên `sshd[4821]`, sửa quyền thư mục `/home/deploy` để `www-data` không thể đọc/ghi. |
| **Persistence (`08:18:05Z`)** | Tệp `/etc/cron.d/health-sync` mới được nạp. | Xóa cron job độc hại, rà soát toàn bộ `/etc/crontab`, `/var/spool/cron/crontabs` và systemd timers trước khi đưa máy chủ trở lại vận hành. |

## Tài liệu tham khảo

1. MITRE ATT&CK. [T1505.003 — Server Software Component: Web Shell](https://attack.mitre.org/techniques/T1505/003/) và [T1098.004 — Account Manipulation: SSH Authorized Keys](https://attack.mitre.org/techniques/T1098/004/).
2. NIST. [SP 800-61 Rev. 2 — Computer Security Incident Handling Guide](https://csrc.nist.gov/pubs/sp/800/61/r2/final). Quy trình phân tích, cô lập (containment), làm sạch (eradication) và phục hồi.
3. OWASP. [Unrestricted File Upload Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).
