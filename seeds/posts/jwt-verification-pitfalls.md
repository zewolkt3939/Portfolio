## 1. Câu hỏi nghiên cứu

JSON Web Token (JWT) và các định dạng token tự chứa (self-contained tokens) cho phép dịch vụ xác minh danh tính mà không cần tra cứu cơ sở dữ liệu ở mỗi request. Tuy nhiên, việc token mang theo cả siêu dữ liệu thuật toán (`header`) lẫn quyền hạn (`payload`) tạo ra một bề mặt lỗi quen thuộc: **nếu bộ xác minh tin tưởng thông tin điều khiển từ chính token chưa được xác thực, hoặc chỉ kiểm tra chữ ký mà bỏ qua ngữ cảnh đích (`aud`, `exp`, `role`), hệ thống sẽ chấp nhận những token giả mạo nào?**

Ghi chép này xây dựng một thí nghiệm nhỏ bằng thư viện chuẩn của Python (`hmac`, `hashlib`, `base64`, `json`) để tách bạch ba lớp kiểm chứng: thuật toán ký, tính toàn vẹn chữ ký và hiệu lực ngữ cảnh của các claim.

## 2. Thiết kế thí nghiệm

Trong [`run_labs.py`](/research/labs/run_labs.py) (hàm `token_experiment`), mình tạo sáu mẫu token dựa trên một khóa HMAC-SHA256 cố định trong bộ nhớ lab và một mốc thời gian tham chiếu xác định (`now_ts = 1789459200`). Hai nhánh kiểm tra được đặt cạnh nhau:

- **Nhánh giải mã lỏng (`loose_verify`):** mô phỏng lỗi kinh điển khi hàm kiểm tra đọc trường `alg` từ header của token trước; nếu `alg == "none"` thì chỉ kiểm tra `exp`, và khi xác minh chữ ký thì không kiểm tra `aud` hay tập quyền cho phép.
- **Nhánh xác minh chặt (`strict_verify`):** cố định danh sách thuật toán cho phép (`HS256`), tính lại HMAC bằng `hmac.compare_digest` hằng thời gian, kiểm tra kiểu số nguyên của `exp`, đối chiếu `aud == "triage-api"` và giới hạn `role` trong tập hợp lệ.

```python
if header.get("alg") != "HS256":
    return False, "alg not allowlisted"
expected = _b64u(hmac.new(secret, f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest())
if not hmac.compare_digest(parts[2], expected):
    return False, "signature mismatch"
if type(payload.get("exp")) is not int or payload["exp"] <= now_ts:
    return False, "expired token"
if payload.get("aud") != required_aud:
    return False, "audience mismatch"
```

Sáu mẫu kiểm thử bao gồm:

1. **`valid analyst token`:** Token hợp lệ, ký bằng `HS256`, còn hạn và đúng `aud: triage-api`.
2. **`alg none downgrade`:** Hạ cấp header thành `{"alg": "none"}` và bỏ trống phần chữ ký để thử vượt qua bước kiểm tra mật mã.
3. **`expired token`:** Chữ ký hợp lệ nhưng thời điểm hết hạn `exp` đã qua.
4. **`cross-service audience`:** Token hợp lệ do cùng hệ thống phát hành cho `billing-service`, được dùng lại trái mục đích trên `triage-api`.
5. **`tampered role with old sig`:** Sửa payload từ `"role": "analyst"` thành `"role": "admin"` nhưng giữ nguyên chữ ký cũ.
6. **`signed with wrong secret`:** Token có cấu trúc đúng nhưng được ký bằng một khóa bí mật khác.

## 3. Kết quả quan sát

[![Sáu mẫu token xác thực: nhánh giải mã lỏng để lọt alg=none, expired và cross-service audience; nhánh xác minh chặt đúng cả 6/6.](/assets/research/jwt-results.svg)](/assets/research/jwt-results.svg)

Hình 1. Kết quả đối chiếu giữa bộ giải mã lỏng và bộ xác minh chặt trên sáu mẫu token từ [`results.json`](/research/labs/results.json).

Nhánh `loose_verify` chỉ xử lý đúng **3/6** trường hợp: nó từ chối được payload bị sửa chữ ký và khóa sai, nhưng lại chấp nhận token hạ cấp `alg: none`, token đã hết hạn khi kiểm tra nhánh chữ ký, và token của dịch vụ khác (`aud: billing-service`).

Nhánh `strict_verify` xử lý đúng **6/6** trường hợp. Mỗi lỗi bị chặn tại đúng ranh giới thiết kế: danh sách trắng thuật toán chặn `alg: none`, `hmac.compare_digest` chặn sửa đổi payload hoặc sai khóa, và bước kiểm tra claim chặn token hết hạn hoặc sai dịch vụ đích.

## 4. Bài học khi kiểm thử và thiết kế xác thực

- **Header của token là dữ liệu chưa xác thực:** Trước khi chữ ký được kiểm chứng thành công, mọi trường trong header (`alg`, `kid`, `jku`) đều do phía gửi kiểm soát. Thuật toán xác minh phải do cấu hình phía server quy định, không bao giờ lấy trực tiếp từ đầu vào.
- **Chữ ký đúng không đồng nghĩa với quyền hợp lệ:** Một token được ký đúng bởi Identity Provider cho dịch vụ A (`aud: billing-service`) sẽ trở thành công cụ leo thang ngang nếu dịch vụ B (`triage-api`) chỉ kiểm tra chữ ký mà không ràng buộc `aud` và `iss`.
- **So sánh hằng thời gian (Constant-time comparison):** Sử dụng `hmac.compare_digest` thay cho toán tử `==` giúp loại bỏ rò rỉ thời gian khi so sánh MAC.

## 5. Tái lập thí nghiệm

Chạy trực tiếp bộ kiểm thử bằng Python 3.10+:

```powershell
python research/labs/run_labs.py
python tools/render_lab_figures.py
```

[Tải mã nguồn lab ↓](/research/labs/run_labs.py)[Xem kết quả JSON ↗](/research/labs/results.json)[Xem bản ghi thực thi ↗](/research/labs/transcript.txt)[Tải biểu đồ SVG ↓](/assets/research/jwt-results.svg)

## Tài liệu tham khảo

1. IETF. [RFC 8725 — JSON Web Token Best Current Practices](https://www.rfc-editor.org/rfc/rfc8725). Khuyến nghị xác minh thuật toán, `aud`, `iss` và `exp`.
2. OWASP. [JSON Web Token for Java / Application Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html). Các mẫu lỗi phổ biến khi xác thực JWT.
3. PortSwigger Web Security Academy. [JWT attacks](https://portswigger.net/web-security/jwt). Phân tích lỗi hạ cấp thuật toán và tiêm nhiễm tham số header.
