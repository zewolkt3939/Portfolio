# Bản lời thoại video demo P-070

Nguồn: kịch bản video của nhóm Eviaura, bản 18/10/2026. Video minh họa thao tác giao diện; kết luận định lượng đọc ở hồ sơ thí nghiệm.

# Phần 1 — Chiến dịch đầu tiên: 00:00–01:20,300

## 00:00:00,400–00:00:08,000

Đây là luồng kiểm thử của RedTeamAI: tạo chiến dịch, lập kế hoạch và chờ người phê duyệt.

## 00:00:08,300–00:00:13,500

Đầu tiên, chọn ứng dụng mục tiêu trong phạm vi được phép kiểm thử.

## 00:00:16,800–00:00:22,600

Bot hướng dẫn giải thích các lựa chọn ngay trên giao diện, giúp người dùng hiểu từng bước cấu hình.

## 00:00:23,000–00:00:28,900

Từ loại tấn công đến nhóm rủi ro, người dùng chủ động xác định nội dung cần kiểm tra.

## 00:00:29,200–00:00:35,500

Tiếp theo, chọn điểm truy cập và kịch bản phù hợp với mục tiêu của chiến dịch.

## 00:00:35,900–00:00:40,100

Trợ lý liệt kê bốn ca kiểm thử có thể chạy.

## 00:00:40,400–00:00:47,200

Trước khi thực thi, kế hoạch hiển thị phạm vi, số yêu cầu dự kiến và mức tác động để xem xét.

## 00:00:47,600–00:00:53,000

Sau khi gửi yêu cầu duyệt, chiến dịch chờ quyết định của người có thẩm quyền.

## 00:00:53,300–00:00:59,700

Người phê duyệt đăng nhập bằng vai trò riêng, rồi mở yêu cầu để kiểm tra kế hoạch.

## 00:01:00,000–00:01:08,800

Từng ca kiểm thử và nội dung gửi đi được xem xét trước khi chấp thuận. Con người vẫn giữ quyền kiểm soát bước thực thi.

## 00:01:09,100–00:01:13,500

Khi được phê duyệt, người kiểm thử mới bắt đầu chạy chiến dịch.

## 00:01:13,700–00:01:20,250

Hệ thống ghi nhận kết quả gửi yêu cầu. Điều này chưa đồng nghĩa tấn công đã thành công.

# Phần 2 — RAG-poison: 01:20,300–02:15,067

## 00:01:20,800–00:01:27,400

Sau lượt kiểm thử đầu tiên, nhóm tạo chiến dịch mới để đánh giá một hướng tấn công khác.

## 00:01:27,800–00:01:34,300

Lần này, mục tiêu là kho tri thức mà hệ thống phòng thủ tra cứu khi phân tích cảnh báo.

## 00:01:34,800–00:01:41,500

Trợ lý đưa ra các kịch bản làm nhiễm độc tri thức. Nhóm chọn hai ca để kiểm thử.

## 00:01:42,000–00:01:48,400

Trước khi chạy, kế hoạch vẫn phải được gửi cho người có thẩm quyền phê duyệt.

## 00:01:48,800–00:01:56,300

Người duyệt xem từng kịch bản và nội dung sẽ đưa vào kho tri thức, rồi mới chấp thuận.

## 00:01:56,700–00:02:02,000

Sau khi được duyệt, chiến dịch được thực thi và ghi lại bằng chứng cho từng ca.

## 00:02:02,300–00:02:07,100

Hệ thống ghi lại tiến trình và bằng chứng của từng ca kiểm thử.

## 00:02:07,500–00:02:14,950

Tài liệu bị đầu độc làm AI hạ mức cảnh báo. Gỡ tài liệu, đánh giá trở lại như đối chứng.

# Phần 3 — AI-SOC: 02:15,067–03:16,267

## 00:02:15,467–00:02:21,167

Tiếp theo, chuyển sang hệ thống phòng thủ để xem các cảnh báo được ghi nhận.

## 00:02:21,467–00:02:27,467

Trợ lý phân tích dấu hiệu chèn lệnh gián tiếp và đưa ra các khuyến nghị xử lý.

## 00:02:27,767–00:02:34,267

Người phân tích mở chi tiết sự cố, xem bằng chứng và xác nhận đây là tấn công.

## 00:02:34,667–00:02:41,167

Mỗi nhận định có dữ liệu cảnh báo và tài liệu hướng dẫn liên quan để đối chiếu.

## 00:02:41,567–00:02:48,067

Các phương án phòng thủ vẫn ở chế độ chạy thử: mô tả hành động, chưa chặn thật.

## 00:02:48,467–00:02:55,367

Từ trợ lý đến danh sách sự cố, người phân tích có thể theo dõi và kiểm tra lại từng nhận định.

## 00:02:55,767–00:03:02,167

Tuy nhiên, một sự kiện lại được đánh giá là thông tin, với giải thích đây là kiểm thử nội bộ đã được duyệt.

## 00:03:02,567–00:03:09,267

Trang Red-Team cho thấy nội dung chèn trong log đã khiến AI đổi nhận định và hạ mức đánh giá.

## 00:03:09,667–00:03:16,167

Trong lab này, AI đã bị đánh lừa. Đây là giá trị của kiểm thử đối kháng.

## Cách đọc bằng chứng

Phần 1 ghi nhận 4 yêu cầu đã gửi, 0 phát hiện được xác nhận. Phần 2 hiển thị hai ca RAG-poison: đối chứng và giai đoạn phục hồi giữ mức high/true; giai đoạn tài liệu bị đầu độc chuyển sang informational/false. Mức 100% trên UI là hai ca của lượt thử được quay, không phải tỷ lệ toàn hệ thống. Phần 3 là recording AI-SOC khác, cho thấy một trường hợp bị nội dung trong log tác động. Thứ tự ghép phục vụ kể chuyện, không khẳng định ba recording cùng campaign hay cùng thời điểm. Phòng thủ vẫn ở chế độ chạy thử.
