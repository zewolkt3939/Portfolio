## 1. Câu hỏi nghiên cứu

Khi một ứng dụng web cho phép người dùng cung cấp URL để tải webhook, ảnh đại diện hoặc nguồn cấp dữ liệu (RSS/JSON), ranh giới bảo mật nằm ở bộ kiểm tra egress. Một sai lầm phổ biến là kiểm tra chuỗi ký tự kiểu đen-trắng (blocklist) đối với `localhost` hoặc `127.0.0.1` trước khi chuyển URL cho thư viện HTTP thực thi. Câu hỏi của ghi chép này là: **vì sao kiểm tra chuỗi trên URL thô dễ bị vượt qua bởi các biểu diễn địa chỉ hợp lệ, và một chính sách egress dựa trên phân giải địa chỉ chuẩn hóa (canonical IP validation) giải quyết những trường hợp biên nào?**

Thí nghiệm này kiểm tra ranh giới phân tích cú pháp URL và kiểm chứng IP theo hướng dẫn phòng chống Server-Side Request Forgery của [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) và chuẩn URI [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986). Toàn bộ phép thử chạy ngoại tuyến với bảng phân giải DNS giả lập, không tạo kết nối mạng ra ngoài.

## 2. Thiết kế thí nghiệm

Hàm `ssrf_experiment` trong [`run_labs.py`](/research/labs/run_labs.py) đối chiếu hai cơ chế kiểm tra trên tám mẫu URL đầu vào:

- **Nhánh kiểm tra chuỗi ngây thơ (`naive_filter`):** chỉ từ chối nếu chuỗi chữ thường chứa `localhost` hoặc `127.0.0.1`.
- **Nhánh chính sách chuẩn hóa (`strict_egress_policy`):** phân tích cấu trúc bằng `urllib.parse.urlsplit`, yêu cầu giao thức `https` trên cổng chuẩn `443`, từ chối thông tin xác thực trong phần authority (`user@host`), phân giải tên miền sang địa chỉ IP rồi kiểm tra thuộc tính `ip.is_global` qua mô-đun chuẩn `ipaddress`.

```python
parsed = urlsplit(url)
if parsed.scheme != "https":
    return False, "disallowed scheme"
if parsed.username or parsed.password or "@" in parsed.netloc:
    return False, "authority credentials rejected"
if parsed.port not in (None, 443):
    return False, "non-standard port"
ip = ipaddress.ip_address(resolved_host)
if not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local:
    return False, "non-global IP blocked"
```

Tám ca kiểm thử đại diện cho các nhóm kỹ thuật thường gặp khi đánh giá SSRF:

| Ca kiểm thử | URL đầu vào | Mục tiêu kiểm chứng |
| --- | --- | --- |
| `public HTTPS feed` | `https://feeds.example.org/advisories.json` | Kiểm thử hồi quy: cho phép nguồn HTTPS công khai hợp lệ. |
| `IPv4 loopback` | `https://127.0.0.1/admin` | Địa chỉ loopback dạng thập phân có dấu chấm cơ bản. |
| `IPv6 loopback` | `https://[::1]/status` | Địa chỉ loopback trên IPv6 thường bị bỏ sót bởi regex IPv4. |
| `decimal loopback` | `https://2130706433/metrics` | Số nguyên 32-bit (`2130706433` = `127.0.0.1`) được nhiều thư viện socket chấp nhận. |
| `cloud metadata link-local` | `https://169.254.169.254/latest/meta-data/` | Dịch vụ metadata đám mây thuộc dải link-local `169.254.0.0/16`. |
| `DNS rebinding / internal A record` | `https://internal-alias.example.org/keys` | Tên miền ngoài trỏ bản ghi A về dải nội bộ `10.24.0.15`. |
| `userinfo authority confusion` | `https://feeds.example.org@10.0.0.1/secret` | Đánh lừa bộ lọc nhìn thấy `feeds.example.org` trong khi host thực là `10.0.0.1`. |
| `file scheme local read` | `file:///etc/passwd` | Thay đổi scheme để đọc tệp cục bộ nếu HTTP client hỗ trợ nhiều giao thức. |

## 3. Kết quả quan sát

[![Tám mẫu URL kiểm thử SSRF: bộ lọc chuỗi chỉ đúng 2/8 ca; chính sách phân giải IP chuẩn hóa đúng cả 8/8 ca.](/assets/research/ssrf-results.svg)](/assets/research/ssrf-results.svg)

Hình 1. Bảng đối chiếu kết quả thực thi giữa bộ lọc chuỗi và chính sách kiểm chứng IP chuẩn hóa từ [`results.json`](/research/labs/results.json).

Nhánh kiểm tra chuỗi chỉ đưa ra quyết định đúng ở **2/8** trường hợp (cho phép URL hợp lệ và chặn `127.0.0.1` viết tường minh). Sáu trường hợp còn lại — bao gồm IPv6 `[::1]`, biểu diễn thập phân `2130706433`, địa chỉ link-local `169.254.169.254`, bản ghi DNS trỏ về IP riêng, cú pháp `@` trong authority và scheme `file://` — đều vượt qua lớp kiểm tra chuỗi.

Ngược lại, nhánh `strict_egress_policy` đạt **8/8** kết quả khớp kỳ vọng trên bộ fixture: duy nhất nguồn HTTPS có IP toàn cục (`93.184.216.34`) được phép đi tiếp, còn bảy mẫu tấn công bị chặn kèm lý do cụ thể.

## 4. Diễn giải và giới hạn trong kiến trúc thực tế

Kết quả cho thấy SSRF không chỉ là bài toán lọc chuỗi đầu vào mà là bài toán **đồng bộ ngữ nghĩa giữa bộ kiểm tra và bộ thực thi kết nối**:

1. **Khác biệt giữa các bộ phân tích URL (Parser Differentials):** Nếu lớp kiểm tra dùng một hàm tách chuỗi tự viết còn thư viện thực thi (như `curl` hoặc `urllib3`) xử lý phần `user@host` hoặc dấu gạch chéo ngược theo cách khác, kẻ tấn công có thể ghép tên miền được phép vào phần userinfo để đánh lừa bộ lọc.
2. **Khoảng trống Time-of-Check to Time-of-Use (TOCTOU) trong DNS Rebinding:** Ngay cả khi ứng dụng phân giải tên miền và kiểm tra `ip.is_global` trước khi gọi `requests.get(url)`, thư viện HTTP vẫn có thể thực hiện truy vấn DNS lần thứ hai. Nếu TTL bằng `0`, lần phân giải thứ hai có thể trả về `127.0.0.1`. Do đó, trong hệ thống thực tế, ứng dụng cần ghim (pin) địa chỉ IP đã xác minh vào tầng transport hoặc đi qua một egress proxy chuyên biệt.
3. **Chuyển hướng HTTP (Redirects):** Một URL công khai hợp lệ ở bước đầu có thể trả về `HTTP 302 Location: http://169.254.169.254/`. Mọi đích chuyển hướng phải đi qua cùng chính sách kiểm tra hoặc tắt hoàn toàn tự động chuyển hướng (`allow_redirects=False`).

## 5. Tái lập thí nghiệm

Từ thư mục gốc của portfolio, chạy lệnh sau để thực thi toàn bộ bộ kiểm thử và tái tạo biểu đồ SVG:

```powershell
python research/labs/run_labs.py
python tools/render_lab_figures.py
```

[Tải mã nguồn lab ↓](/research/labs/run_labs.py)[Xem kết quả JSON ↗](/research/labs/results.json)[Xem bản ghi thực thi ↗](/research/labs/transcript.txt)[Tải biểu đồ SVG ↓](/assets/research/ssrf-results.svg)

## Tài liệu tham khảo

1. OWASP. [Server-Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html). Phân tích kiểm soát lớp ứng dụng và lớp mạng.
2. IETF. [RFC 3986 — Uniform Resource Identifier (URI): Generic Syntax](https://www.rfc-editor.org/rfc/rfc3986). Cấu trúc thành phần authority và quy tắc phân tích URI.
3. Python Software Foundation. [ipaddress — IPv4/IPv6 manipulation library](https://docs.python.org/3.12/library/ipaddress.html). Định nghĩa `is_global`, `is_private`, `is_loopback` và `is_link_local`.
