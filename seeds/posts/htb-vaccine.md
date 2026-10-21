Bài tham khảo được biên soạn dựa trên tài liệu kỹ thuật công khai về machine [Vaccine](https://www.hackthebox.com/machines/vaccine) (Starting Point Tier 2, đã retired trên Hack The Box) và tài liệu chính thức của PostgreSQL. Mục tiêu của ghi chép là phân tích chuỗi nguyên nhân khiến một lỗi tiêm nhiễm SQL ở tầng ứng dụng web dẫn tới thực thi lệnh hệ điều hành và leo thang đặc quyền, cùng cách chặn đứt chuỗi tấn công ở từng lớp.

## 01 / Bức tranh tổng thể của chuỗi lỗi

Trên một hệ thống được phân quyền chặt, lỗ hổng SQL injection ở trang tìm kiếm chỉ nên ảnh hưởng tới dữ liệu mà tài khoản database của ứng dụng được phép đọc. Trong kịch bản của Vaccine, một lỗi đơn lẻ ở tầng web lại đi thẳng tới quyền `root` vì ba điểm yếu nằm nối tiếp nhau:

1. **Tầng Web Application:** Tham số tìm kiếm trên URL được ghép trực tiếp vào câu lệnh SQL mà không qua prepared statement.
2. **Tầng Cơ sở dữ liệu (PostgreSQL):** Ứng dụng kết nối vào database bằng tài khoản có đặc quyền siêu người dùng (`superuser` hoặc thuộc nhóm `pg_execute_server_program`), cho phép dùng câu lệnh `COPY ... FROM PROGRAM` để gọi shell hệ điều hành.
3. **Tầng Hệ điều hành (Sudoers):** Tài khoản hệ thống chạy dịch vụ lại được cấp quyền `sudo` chạy trình soạn thảo `vi` trên một tệp cấu hình mà không khóa khả năng thoát ra shell (`:!/bin/sh`).

[![Sơ đồ chuỗi tấn công trên HTB Vaccine từ SQL injection đến COPY FROM PROGRAM và leo thang đặc quyền qua sudo vi.](/assets/research/htb-vaccine-flow.svg)](/assets/research/htb-vaccine-flow.svg)

Hình 1. Sơ đồ chuỗi bốn bước từ lỗi ghép chuỗi truy vấn tìm kiếm đến leo thang đặc quyền trên máy chủ, đối chiếu với các chốt chặn phòng thủ theo chiều sâu.

## 02 / Khảo sát dịch vụ và xác nhận điểm tiêm nhiễm

Trong môi trường lab được cấp phép, bước đầu tiên là xác định các dịch vụ mạng mở (FTP, SSH, HTTP) và ghi lại trạng thái phản hồi chuẩn của ứng dụng web:

```bash
TARGET="IP_CUA_LAB"
nmap -sC -sV -p 21,22,80 "$TARGET" -oN vaccine-services.txt
```

Sau khi đăng nhập vào bảng điều khiển web trong bài lab, chức năng tìm kiếm gửi tham số qua query string (ví dụ `?search=...`). Để kiểm chứng giả thuyết SQL injection mà không dựa vào phỏng đoán mù, mình so sánh phản hồi giữa một ký tự nháy đơn `'`, một biểu thức đóng bình luận `-- -` và một phép nối hợp lệ:

```text
# Quan sát sự thay đổi số bản ghi trả về hoặc thông báo lỗi DBMS:
http://IP_CUA_LAB/dashboard.php?search=a' ORDER BY 1-- -
http://IP_CUA_LAB/dashboard.php?search=a' UNION SELECT NULL,version(),current_user,NULL-- -
```

Nếu phản hồi hiển thị chuỗi phiên bản của **PostgreSQL** và người dùng hiện tại (`current_user`), nhà phân tích có đủ bằng chứng khẳng định dữ liệu từ `search` đã đi vào bộ phân tích cú pháp SQL.

## 03 / Vì sao PostgreSQL cho phép thực thi lệnh qua `COPY`?

Khác với truy vấn `SELECT` thông thường, PostgreSQL cung cấp lệnh [`COPY`](https://www.postgresql.org/docs/current/sql-copy.html) để chuyển dữ liệu giữa bảng và tệp tin hoặc đầu ra của một chương trình hệ thống (`PROGRAM`). Theo tài liệu bảo mật của PostgreSQL, tùy chọn `PROGRAM` chỉ được phép thực thi bởi `superuser` hoặc người dùng được cấp role `pg_execute_server_program`.

```sql
-- Minh họa cơ chế trong môi trường lab khi tài khoản DB có quyền superuser:
CREATE TABLE IF NOT EXISTS cmd_audit (output text);
COPY cmd_audit FROM PROGRAM 'id; hostname';
SELECT output FROM cmd_audit;
```

Điểm mấu chốt về mặt kiến trúc ở đây không phải là “PostgreSQL không an toàn”, mà là **ứng dụng web đã dùng tài khoản quản trị cơ sở dữ liệu cho các truy vấn đọc thông thường**. Nếu ứng dụng chỉ kết nối bằng một role chỉ có quyền `SELECT` trên bảng dữ liệu nghiệp vụ, câu lệnh `COPY ... FROM PROGRAM` sẽ bị từ chối ngay bởi hệ quản trị cơ sở dữ liệu với lỗi `permission denied`.

## 04 / Từ quyền dịch vụ đến kiểm tra cấu hình `sudo`

Khi kiểm tra quyền hạn của tài khoản hệ điều hành đang chạy dịch vụ (`postgres`) trong lab, lệnh `sudo -l` cho thấy một quy tắc cấp quyền phổ biến nhưng nguy hiểm:

```bash
sudo -l
# Giả sử cấu hình cho phép:
# (ALL) /bin/vi /etc/postgresql/11/main/pg_hba.conf
```

Ý định của người quản trị hệ thống là chỉ cho phép tài khoản `postgres` sửa tệp cấu hình `pg_hba.conf`. Tuy nhiên, trình soạn thảo `vi`/`vim` có tính năng khởi chạy shell con tích hợp sẵn (được ghi nhận trong danh mục [GTFOBins — vi](https://gtfobins.github.io/gtfobins/vi/)). Khi `vi` chạy dưới quyền `root` thông qua `sudo`, bất kỳ lệnh shell nào gọi từ bên trong `:!/bin/sh` đều thừa kế UID `0`.

## 05 / Ma trận khắc phục và kiểm thử lại

Một bản sửa hoàn chỉnh cho kịch bản này cần xử lý cả ba lớp thay vì chỉ vá một điểm:

| Lớp hệ thống | Nguyên nhân gốc | Biện pháp khắc phục | Cách kiểm chứng sau khi sửa |
| --- | --- | --- | --- |
| **Ứng dụng Web** | Ghép chuỗi trực tiếp tham số `search` vào câu lệnh SQL. | Dùng truy vấn tham số hóa (`pg_prepare` / PDO prepared statements). | Thử lại các payload có dấu `'` và `UNION`; kết quả tìm kiếm trả về rỗng, không phát sinh lỗi cú pháp. |
| **PostgreSQL** | Ứng dụng chạy dưới quyền `superuser`. | Tạo tài khoản riêng chỉ có quyền `SELECT`/`INSERT` trên bảng cần thiết; thu hồi `SUPERUSER`. | Kiểm tra `SELECT usesuper FROM pg_user WHERE usename = current_user;` trả về `f`. |
| **Linux Sudoers** | Cho phép chạy trực tiếp `/bin/vi` dưới quyền `root`. | Thay bằng `sudoedit` hoặc thêm tag `NOEXEC:` trong `/etc/sudoers`. | Chạy `sudoedit` kiểm tra sửa file hợp lệ vẫn hoạt động nhưng lệnh `:!/bin/sh` bị hệ điều hành chặn. |

## Tài liệu tham khảo

1. PostgreSQL Global Development Group. [SQL-COPY Documentation](https://www.postgresql.org/docs/current/sql-copy.html). Quy định về quyền `superuser` và `pg_execute_server_program`.
2. GTFOBins. [vi — Sudo shell escape](https://gtfobins.github.io/gtfobins/vi/) và tài liệu `sudoers(5)` về `sudoedit` / `NOEXEC`.
3. OWASP. [SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).

Ghi chú phạm vi: bài viết là tài liệu học tập và phân tích kiến trúc dựa trên machine retired của Hack The Box; không công bố flag và không tuyên bố kết quả từ một phiên khai thác ngoài phạm vi lab.
