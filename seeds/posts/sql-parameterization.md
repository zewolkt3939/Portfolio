## 1. Câu hỏi nghiên cứu

Một phép kiểm thử SQL injection có giá trị cần giải thích được cả nguyên nhân và hiệu quả của bản sửa. Việc một payload không còn hoạt động chưa đủ: ứng dụng có thể đã chặn mọi đầu vào hoặc làm hỏng chức năng hợp lệ. Vì vậy, câu hỏi của ghi chép này là: **tham số hóa có ngăn đầu vào thay đổi cấu trúc truy vấn, đồng thời giữ đúng hành vi với dữ liệu hợp lệ hay không?**

Giả thuyết được kiểm tra trong phạm vi một truy vấn SELECT: khi giá trị được truyền qua placeholder, dấu nháy và chuỗi trông giống cú pháp SQL được xử lý như dữ liệu. Cách tiếp cận này phù hợp với hướng dẫn về parameterized queries của [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html). Ghi chép không đặt giả thuyết về toàn bộ cơ chế xác thực của một ứng dụng.

## 2. Thiết kế thí nghiệm

Môi trường thực thi là Python 3.12.6, SQLite 3.45.3 trên Windows. Một cơ sở dữ liệu `:memory:` chứa hai tài khoản tổng hợp: `alice` và `o'connor`. Trường `secret` chứa token giả để cô lập hành vi truy vấn; đây không phải hướng dẫn lưu mật khẩu. Không có website, tài khoản thật hoặc hệ thống bên ngoài tham gia.

Biến độc lập là cách tạo truy vấn: ghép chuỗi hoặc ràng buộc tham số. Dữ liệu ban đầu, điều kiện tìm kiếm và thứ tự ca thử được giữ nguyên. Biến quan sát gồm quyết định cho phép/từ chối và lỗi cú pháp. Giá trị kỳ vọng được xác định trước trong fixture, dựa trên việc cặp username–token có tồn tại chính xác hay không.

```
# Nhánh đối chứng có lỗ hổng — chỉ trong lab bộ nhớ
query = f"SELECT username FROM users WHERE username='{username}' AND secret='{secret}'"
row = db.execute(query).fetchone()

# Nhánh tham số hóa
row = db.execute(
    "SELECT username FROM users WHERE username=? AND secret=?",
    (username, secret),
).fetchone()
```

Sáu ca bao gồm tài khoản đúng, token sai, tài khoản không tồn tại, tên hợp lệ có dấu nháy, và hai đầu vào làm thay đổi điều kiện truy vấn. Ca có dấu nháy đóng vai trò kiểm thử hồi quy chức năng. Hai payload sử dụng token sai: `alice' --`  và `' OR 1=1 --` . Cả hai chỉ được chạy trên SQLite trong bộ nhớ của tiến trình lab.

## 3. Kết quả quan sát

[![Sáu ca SQLite: nhánh ghép chuỗi cho phép hai ca bypass và gây lỗi với tên chứa dấu nháy; nhánh tham số hóa đúng cả sáu.](/assets/research/sql-results.svg)](/assets/research/sql-results.svg)

Hình 1. Bảng minh họa được tạo từ [kết quả chạy JSON](/research/labs/results.json), không phải ảnh chụp một hệ thống production. Allow/Deny là quyết định của hàm lab.

Nhánh ghép chuỗi cho kết quả đúng ở ba ca thông thường. Tên `o'connor` gây lỗi SQL vì dấu nháy trong dữ liệu làm ngắt literal. Hai payload còn lại trả về một dòng dù token không đúng. Ở nhánh tham số hóa, cả sáu quyết định đều khớp kỳ vọng: hai tài khoản hợp lệ được chấp nhận, bốn trường hợp không hợp lệ bị từ chối.

Con số **6/6** là tỷ lệ ca đạt của bộ kiểm thử được xây dựng cho bài này. Nó không phải “độ an toàn 100%”, cũng không phải ước lượng xác suất ngăn mọi dạng SQL injection. Công khai cả đầu vào lẫn đầu ra giúp người đọc đánh giá phạm vi thay vì chỉ nhìn một tỷ lệ tổng hợp.

## 4. Diễn giải và giới hạn

Sự khác biệt xuất phát từ ranh giới cú pháp. Trong nhánh ghép chuỗi, dữ liệu đầu vào trở thành một phần văn bản SQL được phân tích. Với parameter binding, câu lệnh có cấu trúc cố định còn giá trị được truyền riêng qua API. [Tài liệu sqlite3 của Python](https://docs.python.org/3.12/library/sqlite3.html) mô tả cách sử dụng placeholder thay cho nội suy chuỗi.

Ca tên có dấu nháy cho thấy giá trị của kiểm thử hồi quy: một bản sửa hợp lý phải duy trì chức năng với dữ liệu có ký tự đặc biệt. Nếu chỉ kiểm tra hai payload tấn công, một cách sửa thô như từ chối mọi dấu nháy có thể trông thành công dù làm hỏng tài khoản hợp lệ.

Giới hạn chính là kích thước mẫu nhỏ, lựa chọn ca có chủ đích và một database engine duy nhất. Thí nghiệm không khảo sát second-order injection, ORM, dynamic identifiers hay câu lệnh tạo ở nhiều lớp. Placeholder dùng cho giá trị; tên bảng, tên cột và hướng sắp xếp động cần thiết kế riêng, chẳng hạn ánh xạ qua tập giá trị cho phép. Kết quả không đánh giá session, phân quyền hoặc lưu trữ mật khẩu.

Với quy trình pentest, bài học thực hành là ghi lại yêu cầu ban đầu, chứng minh hành vi sai, chỉ rõ nguyên nhân trong mã và chạy lại cả ca tấn công lẫn ca hợp lệ sau sửa. Một báo cáo tốt phải nối được bằng chứng khai thác với bằng chứng khắc phục.

## 5. Tái lập và mở rộng

Từ thư mục gốc portfolio, chạy lệnh dưới đây bằng Python 3.10 trở lên. Script chỉ dùng thư viện chuẩn, tự tạo dữ liệu tổng hợp và ghi lại phiên bản runtime, thời điểm UTC, SHA-256 mã nguồn, kết quả từng ca. Các tệp kết quả sẽ được cập nhật theo lần chạy mới.

```
python research/labs/run_labs.py
```

[Tải mã Python ↓](/research/labs/run_labs.py)[Dữ liệu và kết quả JSON ↗](/research/labs/results.json)[Bản ghi thực thi ↗](/research/labs/transcript.txt)[Tải hình SVG ↓](/assets/research/sql-results.svg)

Hướng mở rộng là bổ sung Unicode, chuỗi rỗng, kiểu dữ liệu bất thường và kiểm thử các điểm tạo SQL trong ứng dụng thực. Một bước tiếp theo là đưa các ca hồi quy vào bộ test của ứng dụng, nơi session và phân quyền cũng được kiểm chứng.

## Tài liệu tham khảo

1. OWASP. [SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html). Tham khảo về parameter binding và SQL động. Truy cập 15/09/2026.
2. Python Software Foundation. [sqlite3 — DB-API 2.0 interface for SQLite databases](https://docs.python.org/3.12/library/sqlite3.html). Cú pháp placeholder và API thực thi. Truy cập 15/09/2026.
3. Portfolio lab. [run\_labs.py](/research/labs/run_labs.py), hàm `sql_experiment`. Nguồn trực tiếp của thiết kế và số liệu trong bài.

Ghi chú xuất xứ: bài viết và fixture được chuẩn bị với hỗ trợ AI; script đã được thực thi cục bộ khi xây dựng portfolio. Đây là thí nghiệm minh họa mới, không phải thành tích pentest khách hàng của chủ portfolio.

