Bài tham khảo được biên soạn với hỗ trợ AI, dựa trên mô tả của HTB và tài liệu kỹ thuật bên dưới. Các lệnh là hướng dẫn để thực hành trong instance lab của bạn; hình là sơ đồ giải thích, không phải ảnh chụp một lần giải máy.

## 01 / Câu hỏi cần trả lời

Một form đăng nhập có thể chấp nhận người dùng không biết mật khẩu bằng cách nào? [Appointment](https://www.hackthebox.com/machines/appointment) là machine Linux mức Very Easy về SQL injection, được HTB liệt kê là retired. Mình dùng bài này để nối một payload ngắn với lỗi trong cách ứng dụng tạo truy vấn.

1. **Form đăng nhập:** Nhận username và password từ trình duyệt.
2. **Ghép chuỗi thành SQL:** Dấu nháy trong dữ liệu có thể thay đổi cấu trúc truy vấn.
3. **Điều kiện mật khẩu bị bỏ qua:** Ứng dụng nhận được bản ghi và cho phép đăng nhập.

[![Sơ đồ luồng lỗi SQL injection trên form đăng nhập và hướng khắc phục bằng truy vấn tham số hóa.](/assets/research/htb-appointment-flow.svg)](/assets/research/htb-appointment-flow.svg)

Hình 1. Sơ đồ nguyên lý lỗi ghép chuỗi SQL và cơ chế khắc phục bằng prepared statement (không phải mã nguồn trích xuất từ Appointment).

## 02 / Quan sát trước khi thử payload

Khởi động instance trong HTB, kết nối VPN hoặc Pwnbox rồi đặt IP được cấp vào biến bên dưới. Lệnh `-sV` giúp nhận diện dịch vụ; file kết quả giúp đối chiếu lại lần thử. Đây là cách dùng được mô tả trong [tài liệu Nmap](https://nmap.org/book/man-version-detection.html).

```
# Bash trong may ao lab
TARGET="IP_CUA_LAB"
nmap -sV -p 80 "$TARGET" -oN appointment-services.txt
```

Mở trang HTTP của instance. Trước tiên, gửi một cặp thông tin đăng nhập sai và ghi lại thông báo, mã HTTP, URL sau phản hồi và cookie liên quan. Baseline này giúp mình biết phản hồi nào thực sự thay đổi khi đưa payload vào. Nếu đã có phiên đăng nhập cũ, hãy dùng một phiên trình duyệt mới để tránh kết luận nhầm.

## 03 / Vì sao `admin'#` có thể có tác dụng?

[Walkthrough của 0ne-nine9 và ilinor](https://wiki.cjim.app/hackthebox/tier-1/appointment_write-up.pdf) mô tả đường đi qua form đăng nhập. Trong lab, thử username bên dưới với một mật khẩu tùy ý. Gửi qua form hoặc sửa request bằng Burp Repeater, giữ các tham số khác như baseline.

```
Username: admin'#
Password: lab-example
```

Để hiểu cơ chế, giả sử ứng dụng tạo câu lệnh bằng cách ghép trực tiếp hai trường nhập. Đây là truy vấn minh họa, chưa phải kết quả đọc source của máy:

```
SELECT * FROM users
WHERE username = 'admin'#' AND password = 'lab-example';
```

Dấu nháy đóng chuỗi chứa username. Trong MySQL, `#` bắt đầu comment đến hết dòng, khiến phần kiểm tra mật khẩu phía sau không còn được xử lý như điều kiện SQL. Với `--`, MySQL yêu cầu ký tự trắng hoặc ký tự điều khiển ngay sau dấu gạch thứ hai. Chi tiết này nằm trong [tài liệu cú pháp comment](https://dev.mysql.com/doc/refman/8.4/en/comments.html); payload phù hợp với một hệ quản trị chưa chắc hoạt động ở hệ khác.

Nếu ứng dụng dùng một truy vấn tương tự và coi việc trả về bản ghi là đăng nhập thành công, kết quả dự kiến là truy cập được nội dung sau đăng nhập. Hãy kiểm tra nội dung và trạng thái phiên, không chỉ nhìn HTTP 200. Thử lại với thông tin sai trong phiên mới để loại trừ ảnh hưởng của cookie. Nếu phản hồi không đổi, cần kiểm tra request thực gửi đi và cách mã hóa ký tự trước khi kết luận.

## 04 / Từ payload đến một bản sửa có thể kiểm tra

Cách sửa cốt lõi là tách cấu trúc SQL khỏi dữ liệu bằng truy vấn tham số hóa. Luồng xác thực thực tế nên lấy bản ghi theo username rồi kiểm tra password hash bằng thư viện phù hợp, thay vì so sánh mật khẩu dạng rõ trong SQL. [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html) trình bày prepared statement như một biện pháp phòng ngừa chính.

| Ca kiểm tra lại | Điều cần quan sát |
| --- | --- |
| Tài khoản hợp lệ, mật khẩu đúng | Đăng nhập được. |
| Tài khoản hợp lệ, mật khẩu sai | Bị từ chối; không tạo phiên hợp lệ. |
| Username chứa payload | Được xử lý như dữ liệu; không vượt đăng nhập. |
| Username hợp lệ có dấu nháy | Vẫn hoạt động, không bị chặn chỉ vì một ký tự. |

Khi viết finding, mình sẽ lưu request trước/sau, dấu hiệu truy cập trái phép và phạm vi đã chứng minh. Một lần vượt đăng nhập chưa chứng minh được khả năng đọc mọi bảng hay chiếm quyền hệ điều hành. Phần [thí nghiệm SQL cục bộ](/research/sql-parameterization.html) trên portfolio có mã và kết quả chạy thật để so sánh ghép chuỗi với parameter binding; đó là lab SQLite riêng, không phải bản sao Appointment.

## Tài liệu & phạm vi

Thông tin machine được đối chiếu ngày 15/09/2026. Walkthrough PDF được liên kết qua bản lưu công khai; không sao chép hình hay flag của tài liệu. Có thể mở hướng dẫn từ nút Official Writeup trong HTB theo [hướng dẫn Starting Point](https://help.hackthebox.com/en/articles/6007919-introduction-to-starting-point). Bài này chưa có log thực thi trên HTB hoặc bằng chứng hoàn thành của mình.

