# Deploy portfolio lên Amazon Lightsail 4 GB

Sau khi deploy xong, xem [hướng dẫn sử dụng CMS và vận hành website](CMS_USER_GUIDE.md).
Để hiểu luồng xử lý bên trong, xem [nguyên lý hoạt động và kiến trúc](WEBSITE_ARCHITECTURE.md).

Runbook này triển khai toàn bộ `Caddy + FastAPI + PostgreSQL + Umami + Restic`
trên một Lightsail instance. Ví dụ dùng region Singapore (`ap-southeast-1`),
Ubuntu 24.04 LTS và hai hostname:

- `example.com`: portfolio và CMS.
- `analytics.example.com`: Umami.

Thay hai hostname và tên bucket mẫu bằng giá trị thật trước khi chạy.

## 1. Chuẩn bị tài khoản

1. Bật MFA cho AWS root account.
2. Mở **Billing → Budgets** và tạo cảnh báo tại 20 USD, 30 USD và 40 USD.
3. Kiểm tra ngày hết hạn credit tại **Billing → Credits**.
4. Có sẵn một domain. Domain có thể được quản lý tại registrar hiện tại; không
   bắt buộc chuyển domain sang AWS.

## 2. Tạo Lightsail instance

Trong Lightsail console:

1. Chọn **Create instance**.
2. Region: **Singapore / ap-southeast-1**.
3. Platform: **Linux/Unix**.
4. Blueprint: **OS Only → Ubuntu 24.04 LTS**.
5. Networking: **Dual-stack IPv4 + IPv6**.
6. Plan: **4 GB RAM, 2 vCPU, 80 GB SSD**.
7. Đặt tên, ví dụ `bao-portfolio-prod`.
8. Thêm tag `Environment=production` và `Project=portfolio`.

### Gắn static IPv4

Mở **Lightsail → Networking → Create static IP**, chọn đúng region và gắn IP
vào instance. Không trỏ DNS vào địa chỉ động ban đầu vì địa chỉ đó có thể thay
đổi khi stop/start máy.

### Cấu hình firewall

Trong tab **Networking** của instance, sửa cả IPv4 và IPv6 firewall:

| Protocol | Port | Source |
|---|---:|---|
| TCP | 80 | Tất cả |
| TCP | 443 | Tất cả |
| UDP | 443 | Tất cả, cho HTTP/3 |
| TCP | 22 | IP public hiện tại của máy quản trị (`/32`) và bật **Allow Lightsail browser SSH/RDP** |

IP mạng nhà, trường học hoặc 4G thường là IP động. Vì vậy browser-based SSH của
Lightsail là kênh quản trị và khôi phục luôn dùng được; allowlist IP chỉ phục vụ
`scp` hoặc SSH từ terminal cá nhân. Trong rule SSH, chọn **Restrict to IP
address**, nhập IP public hiện tại và đồng thời chọn **Allow Lightsail browser
SSH/RDP**. Khi ISP đổi IP, browser SSH vẫn hoạt động; cập nhật source `/32` trước
khi dùng lại `scp`.

Xem IP public hiện tại trên Windows:

```powershell
(Invoke-RestMethod -Uri "https://checkip.amazonaws.com").Trim()
```

Ví dụ kết quả là `203.0.113.10`, source trong IPv4 firewall sẽ là
`203.0.113.10/32`. Không cần có IP tĩnh tại nhà. Không nên allowlist toàn bộ dải
IP của nhà mạng. Nếu IPv6 của máy cũng thay đổi, không cần thêm rule IPv6 cho
SSH; dùng browser SSH làm đường dự phòng.

Xóa rule SSH cho phép toàn Internet. Không tạo rule cho `5432`, `8000` hoặc
`3000`; ba cổng này chỉ được dùng trong Docker network.

## 3. Trỏ DNS

Tại Lightsail DNS hoặc nhà cung cấp DNS hiện tại, tạo:

| Type | Name | Value |
|---|---|---|
| A | `@` | Static IPv4 của Lightsail |
| A | `analytics` | Static IPv4 của Lightsail |
| CNAME | `www` | `example.com` |

Nếu sử dụng IPv6, thêm bản ghi AAAA cho domain chính và subdomain analytics.
Chỉ thêm AAAA sau khi firewall IPv6 đã có rule 80/443 tương ứng.

Kiểm tra từ máy local:

```powershell
Resolve-DnsName example.com
Resolve-DnsName analytics.example.com
```

Cả hai hostname phải trả về static IP trước khi Caddy xin chứng chỉ HTTPS.

## 4. Tạo gói triển khai ở Windows

Tại thư mục dự án:

```powershell
python tools/build_site.py
python tools/check_site.py
python tools/package_site.py
python tools/package_deploy.py
```

File tạo ra là `build/portfolio-lightsail.tar.gz`. Đây là gói allowlist: không
chứa `.env`, SQLite database, báo cáo thực tập PDF hoặc cache phát triển.

Trước khi upload, cập nhật source `/32` của rule SSH nếu IP mạng đã thay đổi.
Tải default SSH key của Lightsail hoặc dùng key riêng. Với Windows OpenSSH:

```powershell
scp -i "C:\path\LightsailDefaultKey-ap-southeast-1.pem" `
  build/portfolio-lightsail.tar.gz `
  ubuntu@STATIC_IP:/tmp/
```

## 5. Cài Docker và swap

Kết nối bằng Lightsail browser SSH hoặc OpenSSH:

```powershell
ssh -i "C:\path\LightsailDefaultKey-ap-southeast-1.pem" ubuntu@STATIC_IP
```

Trên server:

```bash
sudo mkdir -p /srv/portfolio
sudo tar -xzf /tmp/portfolio-lightsail.tar.gz -C /srv/portfolio
sudo chown -R ubuntu:ubuntu /srv/portfolio
cd /srv/portfolio
sudo ./deploy/lightsail-bootstrap.sh
exit
```

Script cài Docker Engine từ repository chính thức, Docker Compose plugin,
unattended security updates và một swap file 2 GiB dùng khi RAM tăng đột ngột.
Đăng nhập SSH lại để group `docker` có hiệu lực:

```bash
docker version
docker compose version
free -h
```

## 6. Tạo S3 bucket cho backup

Trong S3 console:

1. Tạo bucket có tên duy nhất, ví dụ `bao-portfolio-backup-ACCOUNT_ID`.
2. Region `ap-southeast-1`.
3. Giữ toàn bộ **Block Public Access** ở trạng thái bật.
4. Bật default encryption bằng SSE-S3.
5. Không dùng bucket này để phục vụ ảnh public của website.

Tạo một IAM user dành riêng cho Restic, không dùng root access key:

1. Mở **IAM → Users → Create user**.
2. User name: `portfolio-restic-backup`.
3. Không chọn **Provide user access to the AWS Management Console**.
4. Chọn **Next**. Có thể tạo user chưa có permission ở bước này.
5. Mở user vừa tạo → tab **Permissions**.
6. Chọn **Add permissions → Create inline policy**.
7. Chọn tab **JSON**, xóa JSON mẫu và dán policy bên dưới.
8. Thay `bao-portfolio-backup-ACCOUNT_ID` ở cả hai chỗ bằng chính xác tên S3
   bucket đã tạo, không thêm `s3://` hoặc hostname.
9. Chọn **Next**, đặt policy name `PortfolioResticS3Access`, rồi chọn
   **Create policy**.

Không gắn `AdministratorAccess` hoặc `AmazonS3FullAccess`. Inline policy sau chỉ
cho Restic đọc, ghi và xóa object trong đúng một bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListResticRepository",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::bao-portfolio-backup-ACCOUNT_ID"
    },
    {
      "Sid": "ManageResticObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::bao-portfolio-backup-ACCOUNT_ID/*"
    }
  ]
}
```

Tạo access key cho user này:

1. Mở **IAM → Users → restic-backup**.
2. Vào tab **Security credentials**.
3. Trong **Access keys**, chọn **Create access key**.
4. Chọn use case **Other** hoặc **Command Line Interface (CLI)**.
5. Description: `portfolio-lightsail-restic`.
6. Chọn **Create access key**, rồi tải file CSV hoặc sao chép ngay cả hai giá trị.

AWS hiển thị một cặp như sau:

```text
Access key ID:     AKIA...EXAMPLE
Secret access key: abcdef...EXAMPLE
```

Điền nguyên giá trị sau dấu hai chấm, không giữ ký tự `<` và `>`:

```dotenv
AWS_ACCESS_KEY_ID=AKIA...EXAMPLE
AWS_SECRET_ACCESS_KEY=abcdef...EXAMPLE
```

`AWS_ACCESS_KEY_ID` không phải AWS account ID, bucket name hay username. Secret
chỉ xem được một lần; nếu mất secret, xóa hoặc deactivate key cũ rồi tạo cặp
mới. Key chỉ được đặt trong `/srv/portfolio/.env`; không dùng root access key,
không commit, không gửi qua chat và không chụp màn hình công khai.

## 7. Cấu hình secrets

Toàn bộ bước trong mục này chạy **trực tiếp trên Lightsail**. File production
nằm tại `/srv/portfolio/.env`; không tải file này về workspace, không đưa nó vào
archive và không thay `.env.example` bằng secrets thật.

Trên Lightsail:

```bash
cd /srv/portfolio
cp .env.example .env
chmod 600 .env
```

Tạo các giá trị ngẫu nhiên. Chạy mỗi lệnh và lưu output tương ứng:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
openssl rand -base64 32
```

Mở `.env`:

```bash
nano .env
```

Điền tối thiểu:

```dotenv
POSTGRES_PASSWORD=<random-1>
POSTGRES_DB=postgres
POSTGRES_USER=postgres
PORTFOLIO_DB_PASSWORD=<random-2>
UMAMI_DB_PASSWORD=<random-3>
APP_SECRET_KEY=<random-4>
FIELD_ENCRYPTION_KEY=<output-base64url-32-byte>

PUBLIC_BASE_URL=https://example.com
SITE_ADDRESS=example.com
WWW_ADDRESS=www.example.com
ANALYTICS_ADDRESS=analytics.example.com
ANALYTICS_SCRIPT_URL=https://analytics.example.com/script.js
ANALYTICS_WEBSITE_ID=

NOTION_API_TOKEN=
NOTION_API_VERSION=2026-03-11
SECURE_COOKIES=true
TRUST_PROXY_HEADERS=true

UMAMI_APP_SECRET=<random-5>
UMAMI_TWO_FACTOR_ENCRYPTION_KEY=<output-openssl-base64>

RESTIC_REPOSITORY=s3:s3.ap-southeast-1.amazonaws.com/bao-portfolio-backup-ACCOUNT_ID/portfolio-restic
RESTIC_PASSWORD=<random-6>
AWS_ACCESS_KEY_ID=<restic-user-access-key>
AWS_SECRET_ACCESS_KEY=<restic-user-secret-key>
AWS_DEFAULT_REGION=ap-southeast-1
```

Dùng chuỗi `token_urlsafe` cho password database để connection URL không cần
percent-encode. `FIELD_ENCRYPTION_KEY` phải lấy từ lệnh base64url 32 byte, không
dùng một chuỗi tự đặt.

Kiểm tra không còn placeholder:

```bash
grep -n 'replace-with\|example.com\|ACCOUNT_ID' .env
```

Lệnh không được in ra dòng nào sau khi cấu hình xong.

## 8. Khởi động lần đầu

Nạp biến analytics để build các trang tĩnh, sau đó kiểm tra Compose:

```bash
cd /srv/portfolio
set -a
. ./.env
set +a
python3 tools/build_site.py
python3 tools/check_site.py
python3 tools/package_site.py
docker compose config >/dev/null
docker compose pull postgres umami
docker compose up -d --build postgres app umami caddy
```

Theo dõi trạng thái:

```bash
docker compose ps
docker compose logs --tail=100 postgres app umami caddy
curl --fail https://example.com/health/live
curl --fail https://example.com/health/ready
```

Không nhập URL theo cú pháp Markdown như `[https://domain](https://domain)`;
trong terminal chỉ dùng URL thuần. Nếu endpoint public trả `404`, kiểm tra lần
lượt từ trong app ra ngoài:

```bash
docker compose exec app python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/live').read().decode())"
docker compose exec caddy wget -qO- http://app:8000/health/live
curl -i https://example.com/health/live
```

Hai lệnh đầu phải in `{"status":"ok"}`. Nếu chúng thành công nhưng lệnh cuối
trả `404`, rebuild Caddy từ Caddyfile mới nhất:

```bash
docker compose build caddy
docker compose up -d --force-recreate caddy
docker compose logs --tail=100 caddy
```

Nếu Caddy chưa có HTTPS, kiểm tra DNS và log:

```bash
docker compose logs --tail=100 caddy
```

Không xóa volume Caddy vì volume chứa trạng thái chứng chỉ TLS.

## 9. Tạo admin và nhập sáu bài ban đầu

```bash
docker compose exec app portfolio-cms create-admin --username bao
docker compose exec app portfolio-cms seed-legacy
```

Lệnh đầu yêu cầu password tối thiểu 12 ký tự, sau đó in TOTP provisioning URI
và tám recovery code. Thêm URI vào ứng dụng authenticator và lưu recovery code
ngoại tuyến. Website không có route đăng ký admin thứ hai.

Kiểm tra:

- `https://example.com/admin/login`
- `https://example.com/research.html`
- `https://example.com/vi/research.html`
- `https://example.com/api/v1/posts`

## 10. Khởi tạo Umami

Mở `https://analytics.example.com`. Lần đầu dùng tài khoản mặc định:

- Username: `admin`
- Password: `umami`

Đổi password ngay, bật 2FA, rồi vào **Websites → Add website**:

- Name: `Nguyen Truong Bao Portfolio`.
- Domain: `example.com`.

Sao chép Website ID, cập nhật `ANALYTICS_WEBSITE_ID` trong `.env`, rồi build
lại static image và recreate app để cả trang tĩnh lẫn trang Research nhận ID:

```bash
cd /srv/portfolio
nano .env
set -a
. ./.env
set +a
python3 tools/build_site.py
python3 tools/check_site.py
python3 tools/package_site.py
docker compose build caddy
docker compose up -d --force-recreate app caddy
```

Không bật public share cho dashboard Umami. Caddy gửi `X-Robots-Tag: noindex`
cho toàn bộ analytics subdomain.

## 11. Chạy backup và restore drill

Chạy backup đầu tiên. Script tự khởi tạo Restic repository nếu chưa tồn tại,
dump cả Portfolio lẫn Umami database, lưu uploads, áp dụng retention 7 ngày,
4 tuần, 6 tháng và chạy `restic check`:

```bash
docker compose --profile maintenance run --rm backup
```

Sau đó bắt buộc thử restore:

```bash
docker compose --profile maintenance run --rm \
  --entrypoint portfolio-restore-check backup
```

Restore drill dùng hai database tạm và không ghi đè database đang chạy.

Cài timer backup hằng ngày:

```bash
sudo cp deploy/portfolio-backup.service /etc/systemd/system/
sudo cp deploy/portfolio-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now portfolio-backup.timer
systemctl list-timers portfolio-backup.timer
```

Kiểm tra lịch sử:

```bash
sudo systemctl start portfolio-backup.service
sudo journalctl -u portfolio-backup.service -n 100 --no-pager
```

## 12. Snapshot và kiểm tra vận hành

Sau khi deploy ổn định:

1. Tạo một Lightsail snapshot thủ công mang tên `portfolio-first-production`.
2. Có thể bật automatic snapshot hằng ngày nếu chấp nhận phí lưu trữ snapshot.
3. Mỗi tuần kiểm tra `docker compose ps`, dung lượng đĩa và timer backup.

```bash
df -h
free -h
docker stats --no-stream
docker system df
sudo journalctl -u portfolio-backup.service --since '8 days ago' --no-pager
```

Compose giới hạn log JSON ở ba file, mỗi file 10 MB cho từng service. Không chạy
`docker system prune --volumes` vì lệnh đó có thể xóa dữ liệu database và upload.

## 13. Cập nhật website

Trước mỗi lần cập nhật:

```bash
cd /srv/portfolio
docker compose --profile maintenance run --rm backup
```

Tạo archive mới trên Windows, tải lên `/tmp`, giải nén đè vào
`/srv/portfolio`; `.env` không nằm trong archive nên được giữ nguyên. Sau đó:

```bash
cd /srv/portfolio
set -a
. ./.env
set +a
python3 tools/build_site.py
python3 tools/check_site.py
python3 tools/package_site.py
docker compose build --pull app caddy backup
docker compose up -d app caddy umami postgres
curl --fail https://example.com/health/ready
```

Nếu update thất bại, dùng Lightsail snapshot gần nhất hoặc image GHCR theo commit
SHA như hướng dẫn trong `DEPLOYMENT.md`.

## Checklist hoàn tất

- [ ] Domain chính và analytics subdomain đều có HTTPS hợp lệ.
- [ ] Chỉ 22, 80, 443 TCP và 443 UDP được mở ở Lightsail firewall.
- [ ] SSH 22 bị giới hạn theo IP quản trị.
- [ ] `/health/ready` trả về thành công.
- [ ] Admin password + TOTP hoạt động; recovery code đã lưu ngoại tuyến.
- [ ] Umami default password đã đổi và 2FA đã bật.
- [ ] Sáu bài seed xuất hiện nhưng draft/preview không truy cập công khai.
- [ ] S3 bucket private và IAM key chỉ có quyền trên bucket backup.
- [ ] Backup đầu tiên và restore drill đều thành công.
- [ ] Systemd timer đã được bật.
- [ ] AWS Budget và Lightsail snapshot đã cấu hình.
