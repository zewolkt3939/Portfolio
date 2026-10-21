Bài tham khảo được biên soạn với hỗ trợ AI, dựa trên mô tả machine của HTB và tài liệu Redis. Các bước bên dưới là quy trình đề xuất để kiểm tra trong lab, không phải log của một phiên đã chạy.

## 01 / Từ cổng mạng đến quyền đọc dữ liệu

[HTB mô tả Redeemer](https://www.hackthebox.com/machines/redeemer) là machine Linux mức Very Easy về khảo sát Redis bằng `redis-cli` và các lệnh cơ bản, hiện được liệt kê là retired. Mình tập trung vào câu hỏi: một client chỉ kết nối được qua mạng có thể đi xa đến đâu nếu dịch vụ thiếu giới hạn truy cập?

1. **Nhận diện Redis:** Xác nhận giao thức trên cổng đã tìm thấy.
2. **Kiểm tra xác thực và quyền:** Phân biệt phản hồi PING với quyền đọc dữ liệu.
3. **SCAN → TYPE → GET:** Tìm key, xác định kiểu rồi đọc đúng tài nguyên cần kiểm chứng.

[![Sơ đồ quy trình khảo sát keyspace Redis bằng SCAN và hướng khắc phục bằng Redis ACL.](/assets/research/htb-redeemer-flow.svg)](/assets/research/htb-redeemer-flow.svg)

Hình 1. Sơ đồ quy trình kiểm chứng quyền đọc dữ liệu trên Redis không xác thực và ranh giới bảo vệ bằng ACL.

## 02 / Xác nhận endpoint và phản hồi

Trong máy ảo lab, đặt IP được HTB cấp vào biến. Lệnh bên dưới kiểm tra riêng cổng Redis thường dùng. Nếu không thấy dịch vụ, đối chiếu trạng thái instance, VPN và kết quả khảo sát cổng trước khi thay đổi giả thuyết.

```
TARGET="IP_CUA_LAB"
nmap -sV -p 6379 "$TARGET" -oN redeemer-services.txt
redis-cli -h "$TARGET" -p 6379 PING
```

`PONG` chỉ cho thấy lệnh PING được chấp nhận. Nó chưa chứng minh client có quyền liệt kê key hoặc đọc giá trị. Nếu nhận `NOAUTH` hoặc `NOPERM`, lưu lại phản hồi: đó là thông tin về lớp xác thực hoặc quyền của kết nối hiện tại. Không nên diễn giải mọi lỗi truy cập thành lỗi mạng.

[Tài liệu bảo mật Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/security/) nhấn mạnh giới hạn mạng và xác thực. Mức độ rủi ro phụ thuộc vào cấu hình cùng dữ liệu mà client được phép truy cập, không chỉ việc cổng 6379 đang mở.

## 03 / Tìm key rồi đọc theo kiểu dữ liệu

Mở client và kiểm tra database mặc định. Với bộ dữ liệu nhỏ của lab, quy trình sau giúp nhìn rõ từng quyền cần có:

```
redis-cli -h "$TARGET" -p 6379

# Cac lenh ben trong redis-cli:
SELECT 0
DBSIZE
SCAN 0 MATCH * COUNT 100
```

`SCAN` trả về cursor tiếp theo cùng một nhóm key. Tiếp tục với cursor được trả về cho đến khi cursor là `0`; `COUNT` là gợi ý về lượng công việc, không bảo đảm số key trả về. Có thể gặp key lặp, và dữ liệu đang thay đổi khiến một vòng quét không tương đương snapshot. Những giới hạn này được nêu trong [tài liệu SCAN](https://redis.io/docs/latest/commands/scan/).

Nếu danh sách thực sự có key `flag`, kiểm tra kiểu trước khi đọc. Không mặc định mọi key đều là chuỗi:

```
TYPE flag
# Chi dung GET neu TYPE tra ve string:
GET flag
```

[TYPE](https://redis.io/docs/latest/commands/type/) trả về kiểu của key, hoặc `none` nếu key không tồn tại. [GET](https://redis.io/docs/latest/commands/get/) đọc giá trị chuỗi; dùng nó cho một hash hay list sẽ gây lỗi kiểu. Nếu không thấy key dự kiến, hãy dựa vào kết quả liệt kê và đề bài hiện tại thay vì coi tên trong hướng dẫn là bằng chứng rằng key đó tồn tại.

Kết quả cần xác nhận là client chưa cung cấp credential vẫn đọc được dữ liệu thuộc mục tiêu lab. Lưu phiên bản client, IP instance, thời điểm, lệnh và phản hồi đã che flag. Thao tác đọc thành công không đủ để kết luận có quyền ghi, thực thi lệnh hay chiếm quyền hệ điều hành.

## 04 / Một bản sửa cần chặn đúng đường truy cập

Mình sẽ bắt đầu từ việc xác định ứng dụng nào thực sự cần kết nối Redis, rồi giới hạn mạng và cấp quyền theo nhu cầu đó. Dùng ACL cho từng tài khoản ứng dụng, giới hạn lệnh và key, đồng thời rà soát quyền của tài khoản mặc định. Redis có thể phục vụ nhiều vai trò; quy tắc dành cho cache đọc không nhất thiết phù hợp với hàng đợi cần ghi.

| Vị trí kiểm tra | Điều cần xác nhận |
| --- | --- |
| Client ngoài mạng được phép | Không kết nối được tới dịch vụ. |
| Client được kết nối nhưng chưa xác thực | Không đọc được key cần bảo vệ. |
| Tài khoản ứng dụng | Thao tác cần thiết vẫn chạy; lệnh ngoài quyền bị chặn. |
| Kết nối cần bảo vệ trên đường truyền | Dùng TLS với cấu hình và xác minh phù hợp. |

Thông điệp quan trọng của bài là quyền truy cập cần được kiểm tra ở cả mạng lẫn dịch vụ. Một lớp cho phép kết nối không có nghĩa lớp còn lại nên cho phép đọc mọi dữ liệu. Tham khảo [hướng dẫn ACL của Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/) khi xây dựng chính sách cho từng ứng dụng.

## Tài liệu & phạm vi

Nguồn được đối chiếu ngày 15/09/2026. Quy trình SCAN ở đây là lựa chọn kỹ thuật của bài viết, không được gán là chuỗi lệnh nguyên bản trong walkthrough HTB. Chưa có kết quả chạy trên instance, giá trị flag hay bằng chứng hoàn thành của mình.

