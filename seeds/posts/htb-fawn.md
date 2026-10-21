Bài tham khảo được biên soạn với hỗ trợ AI. Luồng giải dựa trên tài liệu Fawn của 0ne-nine9; phần cách lưu bằng chứng và kiểm tra lại là hướng dẫn bổ sung. Chưa chạy instance HTB khi biên soạn bài.

## 01 / Một cổng mở cho biết điều gì?

Fawn thuộc những bài Linux cơ bản được giới thiệu trong [Starting Point của HTB](https://www.hackthebox.com/blog/cybersecurity-awareness-month-starting-point). Điểm cần học ở đây là cách kiểm tra cấu hình và quyền đọc dữ liệu. Một dịch vụ FTP có thể hoạt động đúng giao thức nhưng vẫn để lộ file do cấp quyền quá rộng.

1. **TCP / 21:** Xác nhận endpoint đang cung cấp dịch vụ FTP.
2. **Đăng nhập anonymous:** Kiểm tra có cần tài khoản cá nhân hay không.
3. **Liệt kê rồi tải file:** Tách quyền xem thư mục khỏi quyền đọc nội dung.

[![Sơ đồ quy trình kiểm tra quyền truy cập anonymous trên FTP và tách bạch các lớp kiểm soát.](/assets/research/htb-fawn-flow.svg)](/assets/research/htb-fawn-flow.svg)

Hình 1. Sơ đồ các bước kiểm tra quyền truy cập FTP và hướng cấu hình thu hẹp phạm vi đọc dữ liệu.

## 02 / Xác nhận dịch vụ và kiểu truy cập

Trong máy ảo thực hành đã kết nối với HTB, đặt IP instance vào biến. Đầu tiên nhận diện dịch vụ, sau đó chạy riêng script kiểm tra anonymous để dễ hiểu kết quả từng bước.

```
TARGET="IP_CUA_LAB"
nmap -sV -p 21 "$TARGET" -oN fawn-services.txt
nmap -p 21 --script ftp-anon "$TARGET" -oN fawn-anonymous.txt
```

Theo [tài liệu ftp-anon](https://nmap.org/nsedoc/scripts/ftp-anon.html), script thử đăng nhập anonymous và liệt kê thư mục nếu được chấp nhận. Kết quả cho biết tài khoản này có quyền gì tại thời điểm thử. Nó chưa đủ để kết luận đọc được mọi file hay ghi được dữ liệu lên máy.

## 03 / Kiểm tra thủ công đến quyền đọc file

[Fawn Write-up, tác giả 0ne-nine9](https://wiki.cjim.app/hackthebox/tier-0/fawn_write-up.pdf) mô tả đăng nhập bằng tài khoản anonymous rồi lấy file `flag.txt`. Có thể theo dõi từng bước bằng FTP client:

```
mkdir -p fawn-evidence
cd fawn-evidence
ftp "$TARGET"

# Nhap khi client hoi ten va mat khau:
# Username: anonymous
# Password: lab@example.invalid

# Cac lenh ben trong FTP client:
pwd
ls
get flag.txt
bye

# Quay lai shell:
cat flag.txt
```

Địa chỉ email ở trên chỉ là chuỗi mẫu gửi theo quy ước của anonymous FTP. Khi thực hành, lưu phản hồi đăng nhập và phản hồi của lệnh tải file. Nếu tải thành công, đối chiếu nội dung với mục tiêu của lab rồi nộp flag trực tiếp trên HTB; không đưa giá trị flag vào write-up công khai.

Mình tách ba kết luận: đăng nhập được, thấy tên file và đọc được nội dung. Nếu `ls` chạy nhưng `get` lỗi, kiểm tra quyền đọc trên server và quyền ghi ở thư mục local. Nếu đăng nhập được nhưng liệt kê bị treo, kiểm tra kết nối dữ liệu FTP và chế độ active/passive. Không nên bật quyền quản trị trên máy local chỉ để bỏ qua một lỗi chưa hiểu.

Trong biên bản kiểm thử, tên file và một mẫu nội dung đã che thông tin thường hữu ích hơn ảnh chụp toàn bộ thư mục. Chỉ kết luận lộ dữ liệu khi đã xác nhận tài khoản không xác thực đọc được tài nguyên vốn cần hạn chế truy cập.

## 04 / Sửa quyền truy cập và kiểm tra lại

Nếu dịch vụ không cần cung cấp file công khai, tắt anonymous. Với vsftpd, tùy chọn liên quan là `anonymous_enable=NO`. Nếu vẫn cần vùng tải xuống công khai, hãy giới hạn thư mục và chỉ đặt dữ liệu được phép công bố vào đó. Các tùy chọn cấp quyền được mô tả trong [tài liệu cấu hình vsftpd](https://security.appspot.com/vsftpd/vsftpd_conf.html).

Truyền dữ liệu qua kênh mã hóa và kiểm soát người được đọc file là hai việc riêng. FTPS hoặc SFTP giúp bảo vệ dữ liệu trên đường truyền, nhưng một tài khoản anonymous vẫn có thể đọc file nếu server cho phép. SFTP là giao thức truyền file qua SSH, không phải tên khác của FTP.

| Ca kiểm tra | Kết quả mong đợi sau sửa |
| --- | --- |
| Đăng nhập anonymous khi không có nhu cầu công khai | Bị từ chối. |
| Đọc file nhạy cảm từ vùng công khai | Không thể truy cập. |
| Tài khoản được cấp quyền tải file hợp lệ | Vẫn tải được file cần thiết. |
| Rà soát log truyền file | Đối chiếu được phiên và thao tác đã kiểm thử. |

Bài học mình muốn giữ lại là luôn đi từ quan sát đến tác động cụ thể. “FTP đang mở” chỉ là thông tin khảo sát; “người không có tài khoản đọc được file cần bảo vệ” mới mô tả rõ vấn đề phân quyền.

## Tài liệu & phạm vi

Nguồn được kiểm tra ngày 15/09/2026. PDF Fawn là bản lưu công khai của walkthrough có ghi tên tác giả; hình minh họa trong bài được dựng lại bằng HTML, không sao chép screenshot gốc. Bài chưa có transcript thực thi hoặc bằng chứng mình đã hoàn thành machine. Tham khảo thêm [RFC 959](https://www.rfc-editor.org/rfc/rfc959) về kết nối điều khiển, dữ liệu và mã phản hồi FTP.

