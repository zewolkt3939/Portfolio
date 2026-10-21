## 1. Ít cảnh báo hơn có phải tốt hơn?

Trong một hàng đợi SOC, hai bản ghi giống nội dung có thể là cùng một sự kiện được giao lại, hoặc hai lần hoạt động thực sự khác nhau. Nếu pipeline xóa cả hai loại như nhau, dashboard có vẻ yên tĩnh hơn nhưng bằng chứng về tần suất và phạm vi hoạt động đã bị mất. Câu hỏi của bài viết là: **chọn khóa deduplication như thế nào để phân biệt việc giao lại với việc xảy ra lại?**

Ghi chép tách hai thao tác: deduplication loại bỏ bản giao lặp của cùng sự kiện; correlation liên kết nhiều sự kiện để tạo ngữ cảnh. Một chuỗi đăng nhập thất bại liên tiếp có thể cần correlation. Xóa hết những dòng giống nhau trước khi đếm sẽ làm thay đổi dữ liệu mà quy tắc phân tích nhìn thấy.

Ví dụ đầu vào trong [tài liệu Wazuh Active Response](https://documentation.wazuh.com/current/user-manual/capabilities/active-response/custom-active-response-scripts.html) chứa các trường như định danh cảnh báo, agent, rule và timestamp. Bài này mượn ý tưởng về các trường đó để thiết kế fixture riêng; không khẳng định tuple sử dụng ở đây là khóa chuẩn được Wazuh bảo đảm cho mọi cấu hình.

## 2. Dữ liệu và phép đối chứng

Script tạo tám sự kiện `evt-00` đến `evt-07`, phân bố luân phiên cho `host-0` và `host-1` dưới một manager giả lập. Timestamp cách nhau một giây. Cả tám cùng mang rule `5710` và nội dung `Failed authentication for lab-user`. Sau đó, bốn bản sao của các sự kiện 00, 02, 04 và 06 được thêm vào luồng. Có 12 lần giao nhưng chỉ tám sự kiện nguồn.

Ground truth được biết từ lúc tạo fixture: tám ID khác nhau biểu diễn tám lần xảy ra độc lập. Hai thuật toán xử lý cùng tập đầu vào, không thay đổi thời gian hay nội dung giữa các nhánh. Khóa thứ nhất chỉ dùng rule và văn bản; khóa thứ hai dùng phạm vi nguồn và ID sự kiện.

```
# Khóa theo nội dung
key = (event["rule"]["id"], event["full_log"])

# Khóa định danh trong fixture này
key = (event["manager"], event["agent"]["id"], event["id"])

# Chỉ giữ lần giao đầu tiên của cùng một định danh
if key not in seen:
    kept.append(event)
    seen.add(key)
```

Chỉ số chính là số sự kiện riêng biệt còn lại so với ground truth. Chỉ số phụ là số lần giao dư được loại bỏ. Chúng được quan sát bằng tập ID giữ lại và audit trail của từng quyết định; không dùng số dòng giảm được làm tiêu chí duy nhất.

## 3. Kết quả phát lại

[![12 bản ghi: khóa nội dung giữ 1/8 sự kiện riêng biệt, khóa định danh giữ 8/8 và loại 4 bản giao lặp.](/assets/research/dedup-results.svg)](/assets/research/dedup-results.svg)

Hình 1. Bảng kết quả dựng từ dữ liệu thực thi. Tất cả sự kiện là tổng hợp; số lượng giữ lại không phải số đo tại SOC thật.

Khóa theo nội dung tạo một nhóm duy nhất vì rule và thông điệp đều giống nhau. Nó giữ lại một sự kiện, mất bảy sự kiện riêng biệt: tỷ lệ giữ lại là **1/8 = 12,5%**. Tổng 11 dòng bị loại gồm bốn lần giao lặp và bảy lần xảy ra cần giữ. Một chỉ số “giảm 91,7% số dòng” sẽ che khuất lỗi này nếu đứng một mình.

Khóa định danh giữ tám sự kiện và loại đúng bốn bản giao lại. Tỷ lệ giữ lại trong fixture là **8/8**; số bản giao trùng còn lại bằng không. Các assertion kiểm tra cả số lượng và tập ID, vì chỉ kiểm tra độ dài có thể bỏ sót trường hợp giữ nhầm bản ghi khác.

Đây là phản ví dụ có chủ đích, không phải ước lượng hiệu suất trung bình. Một bộ đầu vào như vậy đã đủ bác bỏ giả định “nội dung giống nhau luôn là cùng sự kiện”. Tuy nhiên, kết quả chưa đủ để kết luận khóa định danh đã phù hợp mọi nguồn log.

## 4. Ý nghĩa đối với điều tra và thiết kế

Trong điều tra, thời gian và số lần lặp là dữ liệu. Nếu hai host tạo cùng lỗi xác thực, giữ một dòng đại diện có thể làm sai phạm vi ảnh hưởng. Nếu cần gộp hiển thị, hệ thống nên giữ số lần xuất hiện, thời điểm đầu/cuối và liên kết tới sự kiện gốc. Một bản tóm tắt có thể phục vụ triage trong khi kho bằng chứng vẫn giữ dữ liệu để tra cứu.

Khóa định danh phụ thuộc hợp đồng của nguồn. Nếu ID có thể tái sử dụng sau restart, cần thêm namespace hoặc epoch thích hợp. Nếu nhiều manager dùng chung ID, phải tránh xung đột phạm vi. Nếu thiếu ID, băm nội dung chuẩn hóa là một lựa chọn cần đánh giá: hai sự kiện thật vẫn có thể mang cùng nội dung, kể cả timestamp ở độ phân giải thấp.

Thí nghiệm dùng tập `seen` trong bộ nhớ, không xử lý cạnh tranh giữa worker, crash recovery hay giới hạn bộ nhớ. Pipeline thực tế còn cần chính sách lưu khóa, TTL và thao tác nguyên tử. TTL quá ngắn có thể cho bản giao muộn đi qua; giữ khóa vô hạn có chi phí và rủi ro với ID tái sử dụng. Những quyết định đó cần workload và mô hình lỗi cụ thể.

Thực nghiệm này không đo tốc độ, precision phát hiện tấn công hoặc thời gian triage. Ý nghĩa của nó nằm ở tính đầy đủ của dữ liệu đầu vào: cần bảo toàn các sự kiện riêng biệt trước khi đánh giá chất lượng phân tích ở các lớp sau.

## 5. Tái lập và bước tiếp theo

```
python research/labs/run_labs.py
```

Môi trường lần chạy ghi nhận: Python 3.12.6 trên Windows. Trường `dedup.input` trong JSON chứa đủ 12 bản giao; `dedup.audit` ghi quyết định giữ hoặc loại của khóa định danh. Không cần Wazuh, dữ liệu SIEM hay kết nối mạng để chạy lại.

[Tải mã Python ↓](/research/labs/run_labs.py)[Fixture và audit trail ↗](/research/labs/results.json)[Bản ghi thực thi ↗](/research/labs/transcript.txt)[Tải hình SVG ↓](/assets/research/dedup-results.svg)

Bộ thử tiếp theo nên gồm ID tái sử dụng, nhiều manager, sự kiện đến sai thứ tự, giao lặp sau TTL và thiếu trường. Khi tích hợp vào pipeline, có thể đối chiếu tập ID trước và sau xử lý, lưu lý do loại bỏ, rồi mới đánh giá ảnh hưởng tới rule correlation.

## Tài liệu tham khảo

1. Wazuh. [Custom active response scripts](https://documentation.wazuh.com/current/user-manual/capabilities/active-response/custom-active-response-scripts.html). Ví dụ cấu trúc cảnh báo JSON. Truy cập 15/09/2026.
2. Portfolio lab. [run\_labs.py](/research/labs/run_labs.py), hàm `dedup_experiment`; [kết quả thực thi](/research/labs/results.json). Nguồn trực tiếp của fixture và số liệu.
3. Bối cảnh portfolio: [AI-assisted Wazuh triage](/projects/ai-wazuh-triage.html). Lab mới độc lập với việc đánh giá mã nguồn hoặc vận hành của dự án này.

Ghi chú xuất xứ: fixture tổng hợp và bài viết được chuẩn bị với hỗ trợ AI; mã đã được chạy cục bộ. Không sử dụng log khách hàng và không quy kết kết quả này cho Wazuh hay một SOC production.

