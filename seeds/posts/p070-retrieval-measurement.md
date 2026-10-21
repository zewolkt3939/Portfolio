Hybrid retrieval thu hồi nhiều nhóm testcase liên quan hơn keyword trên bộ 24 query của P-070: Recall@10 tăng từ 50,00% lên 83,33%. Con số này trả lời câu hỏi về truy hồi trong bộ smoke đã gán nhãn, chưa trả lời câu hỏi hệ thống tấn công tốt hơn bao nhiêu.

Mình viết lại phép đo từ hồ sơ nhóm ngày 10/10/2026 vì đây là một ví dụ dễ nhầm giữa chất lượng tìm nguồn và chất lượng một hệ thống AI hoàn chỉnh. Bài dành cho người đang làm RAG hoặc xây thư viện testcase, cần đọc một benchmark mà không đánh đồng mọi metric với accuracy.

## So sánh chỉ có ý nghĩa khi query và corpus được giữ nguyên

Hồ sơ runtime ghi 5.730 case được gom thành 1.609 nhóm nội dung và tạo 1.611 chunk/vector 1.536 chiều. Profile sử dụng `text-embedding-3-small`, với chunking `cl100k-480-60-v2`. Đây là metadata của lần nạp được ghi nhận, không phải một lần nạp lại khi viết bài.

Hai chế độ keyword và hybrid được so trên cùng bộ 24 query tiếng Anh/Việt, cùng corpus và runtime filter. Cả 24 query của lượt hybrid không fallback sang keyword. Điều kiện này giúp tránh một thay đổi dữ liệu bị hiểu nhầm thành tiến bộ của thuật toán.

Các nhãn relevance ở cấp **group**. Nếu hai chunk cùng đại diện một testcase, đếm chúng như hai kết quả hữu ích độc lập có thể làm metric đẹp hơn thực chất. Đọc đơn vị đánh giá trước khi đọc phần trăm là bước quan trọng đầu tiên.

## Recall@k và MRR mô tả những mặt khác nhau của truy hồi

Recall@k đo tỷ lệ nhóm liên quan trong nhãn được tìm thấy ở k kết quả đầu. Một query có nhiều group liên quan có thể được chấm theo tỷ lệ, không chỉ đúng hoặc sai. MRR ưu tiên thứ hạng của kết quả liên quan đầu tiên; nó không thay thế việc thu hồi đầy đủ nhiều nhóm nguồn.

| Metric | Keyword | Hybrid | Cách đọc trong bộ thử này |
|---|---:|---:|---|
| Recall@1 | 45,83% | 62,50% | Tỷ lệ relevance được thu hồi ở kết quả đầu |
| Recall@5 | 50,00% | 75,00% | Mở rộng cửa sổ tới 5 kết quả |
| Recall@10 | 50,00% | 83,33% | Mở rộng cửa sổ tới 10 kết quả |
| MRR | 0,4871 | 0,7160 | Vị trí của kết quả liên quan đầu tiên |

![So sánh keyword và hybrid trên cùng 24 query, với Recall@1, Recall@5, Recall@10 và MRR](/assets/p070/retrieval-results.svg)

Hình 1. Biểu đồ dựng lại từ bảng số liệu trong `eval/results/hybrid-retrieval/README.md`. Trục Recall và MRR đều nằm trong khoảng 0–1, nhưng là các metric khác nhau; không cộng hoặc lấy trung bình chúng để tạo “điểm AI”.

Chênh lệch Recall@10 là **33,33 điểm phần trăm**, không phải “tăng 33,33%” theo cách tính tương đối. Việc ghi rõ đơn vị giúp tránh phóng đại hoặc diễn giải sai thay đổi.

## Query khó cho thấy điểm tổng hợp đang che điều gì

Theo hồ sơ, hybrid Recall@10 đạt 79,17% cho nhóm query tiếng Anh và 87,50% cho tiếng Việt. Tuy nhiên, số query nhỏ và relevance label chưa phải holdout độc lập, nên chưa thể kết luận hệ thống luôn tốt hơn với tiếng Việt.

Theo family, prompt injection và jailbreak đều có Recall@10 66,67%, thấp hơn RAG poisoning và Tool IAM trong bộ này. Hai family sau chỉ có 6 query mỗi family. Đây là lý do mình ưu tiên xem lỗi theo nhóm thay vì dùng một số trung bình để mô tả mọi loại testcase.

Các query chưa thu hồi đủ mọi group liên quan trong top 10 được hồ sơ liệt kê riêng. Đó là điểm bắt đầu cho phân tích lỗi: nhãn có đầy đủ không, case gần nghĩa nào đang cạnh tranh, metadata filter có loại nhầm nguồn không. Chưa có bằng chứng để quy tất cả lỗi cho embedding model.

## Recall tốt hơn chưa chứng minh generation hoặc attack success tốt hơn

Một testcase được retrieve có thể chỉ dùng làm tài liệu tham khảo. Hồ sơ ghi corpus ở trạng thái `review_only`; nó không tự cấp adapter hoặc quyền thực thi. Chat smoke dùng target context fixture trong bộ nhớ và không gửi request tấn công đến website.

Muốn đo tác động xuống generation hoặc verdict, cần thêm một tầng đánh giá với đầu ra, nhãn, đối chứng và oracle tương ứng. Với tấn công, còn phải chứng minh delivery và hành vi mục tiêu. Bài [ranh giới bằng chứng trong P-070](/research/p070-evidence-boundaries.html) mô tả chuỗi quan sát đó.

Việc tăng Recall@10 cũng có đánh đổi: đưa nhiều đoạn vào context hơn có thể làm tăng lượng dữ liệu và nhiễu, nhưng lượt benchmark này chưa có phép đo đầy đủ về chi phí hay latency đầu-cuối. Mình không gán con số cho phần chưa đo.

## Bước kiểm tra tiếp theo là một bộ validation riêng

Hồ sơ ngày 10/10 có query hash khác report embedding ngày 07/10. Vì vậy, so hai bảng qua hai ngày mà không đối chiếu query/corpus sẽ không tạo được một kết luận before/after sạch.

Một quy trình tiếp nối hợp lý là khóa corpus và relevance judgments, tách validation, rồi so keyword/hybrid theo cùng filter và latency budget. Các query dùng để tinh chỉnh chunking, RRF hoặc reranker nên được phân biệt với query dùng để báo kết quả cuối.

Trước khi thay model, hãy thử kiểm tra độ đầy đủ của nhãn và mở một vài trường hợp mất nguồn. Một cải thiện trong cách đo có thể giúp tìm đúng vấn đề mà việc đổi model chưa giải quyết.

## Nguồn và dữ liệu dùng trong bài

1. Hồ sơ nhóm: `eval/results/hybrid-retrieval/README.md`, ngày 10/10/2026; bảng metric được đối chiếu với mô tả keyword/hybrid trong cùng thư mục.
2. Tổng hợp phạm vi phép đo: `eval/results/report.md`.
3. [Số liệu tổng hợp đã chọn để xuất bản](/assets/p070/evaluation-summary.json).
4. [Đường dẫn nguồn và hash tài liệu](/assets/p070/sources.json).
5. [Hồ sơ dự án và phần việc từng thành viên](/projects/p070-ai-redteam-soc.html).

Bài do Nguyễn Trường Bảo biên soạn từ kết quả của nhóm Eviaura, có hỗ trợ AI trong khâu trình bày. Phần benchmark retrieval phía Red không được trình bày như thành tích triển khai cá nhân của mình. Không gọi lại embedding API hoặc chạy một thí nghiệm tấn công mới để xuất bản bài này.
