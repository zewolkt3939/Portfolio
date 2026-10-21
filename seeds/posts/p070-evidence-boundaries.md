Một request trả HTTP 200 mới chỉ cho biết website đã xử lý yêu cầu. Để kết luận một LLM trong SOC bị prompt injection, cần chứng minh thêm rằng dữ liệu đối kháng đã đi vào context và làm thay đổi quyết định so với điều kiện đối chứng. Đây là khoảng cách giữa “gửi được payload” và “quan sát được hành vi bị dẫn dắt” mà nhóm Eviaura phải xử lý trong P-070.

Bài này dành cho sinh viên và kỹ sư đang thiết kế thí nghiệm AI security. Mình tổng hợp từ hồ sơ của nhóm, trong đó phần đóng góp được ghi nhận của mình tập trung vào AI-SOC, Wazuh, website lab và bằng chứng phía Blue. Các kết quả bên dưới là bản ghi có ngày trong repo, không phải một lượt kiểm thử mới.

## Một chuỗi xử lý có nhiều ranh giới tin cậy

P-070 là lab mô phỏng trong dự án AI20K, phục vụ đề tài nhóm cho Vinsoc. Website bất động sản là bề mặt tạo dữ liệu; Wazuh phát hiện sự kiện; AI-SOC v2 dùng LLM để hỗ trợ phân loại và giải thích; AI-REDTEAM điều phối các ca kiểm thử có phạm vi và bước phê duyệt. Response phía SOC được giữ ở chế độ dry-run.

![Các mức bằng chứng từ HTTP request tới thay đổi hành vi mô hình](/assets/p070/evidence-ladder.svg)

Hình 1. Sơ đồ khái niệm biên soạn từ luồng triển khai và tiêu chí đánh giá của nhóm. Mỗi ô là một quan sát cần xác minh riêng; mũi nối không tự chứng minh dữ liệu đã đi qua toàn chuỗi.

Trong một thí nghiệm indirect prompt injection, chỉ dẫn không đến trực tiếp từ người đang giao việc cho LLM. Nó được đặt trong nội dung bên ngoài mà hệ thống có thể đọc, chẳng hạn trang web hoặc dữ liệu log. Cách phân biệt này phù hợp với mô tả của [OWASP LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/).

Điểm cần quan sát là lúc nội dung từ nguồn bên ngoài được diễn giải thành chỉ dẫn. Một dòng log có chuỗi đáng ngờ vẫn có thể được mô hình đọc như dữ liệu để phân tích, thay vì mệnh lệnh phải làm theo.

## HTTP 200, Wazuh alert và verdict trả lời ba câu hỏi khác nhau

Mình tách bằng chứng thành bốn mức để tránh gộp những phép đo không cùng ý nghĩa.

| Mức | Quan sát cần có | Điều có thể kết luận |
|---|---|---|
| Gửi và nhận | Request/response, thời điểm, mã HTTP | Target đã tiếp nhận hoặc xử lý yêu cầu |
| Phát hiện | Alert tương ứng với request, nguồn và thời gian | Sự kiện đã được tầng giám sát ghi nhận |
| Tiếp xúc với mô hình | Prompt/context hoặc provenance có thể đối chiếu | Nội dung thử nghiệm đã có mặt tại ranh giới LLM |
| Thay đổi hành vi | Verdict, đối chứng, tiêu chí chấm và lượt phục hồi | Có hay chưa có bằng chứng quy thay đổi cho tác động đối kháng |

Báo cáo manual E03 ghi nhận request HTTP 200 và timeline đã gửi payload nhưng còn chờ bằng chứng phía Blue. Nhãn kết luận trong hồ sơ là **INCONCLUSIVE** đối với hiệu quả khai thác. Phần giao diện và truy vết gửi request được ghi nhận riêng; HITL chưa được kiểm thử trong ca đó.

Đây là một kết quả hữu ích: nó chỉ đúng phần bằng chứng còn thiếu để lần sau có thể nối chuỗi. Nếu đổi nhãn thành “thành công” chỉ vì request trả 200, phép đo sẽ đánh giá chất lượng gửi HTTP thay vì khả năng tác động lên LLM.

## Phép thử cần giữ ổn định bộ nhớ và điều kiện đối chứng

AI-SOC có lịch sử theo IP, analyst feedback và dữ liệu RAG. Cùng một đầu vào có thể cho kết quả khác khi lịch sử thí nghiệm thay đổi. Vì vậy, một cặp thử cần ghi tối thiểu model/profile, trạng thái memory, nguồn dữ liệu, thời điểm, ID đối chiếu và tiêu chí đánh giá trước khi chạy.

Mình ưu tiên thiết kế một cặp control/payload có cùng dạng sự kiện, chỉ thay phần đang cần khảo sát. Đối chứng phải đủ hợp lệ để hệ thống xử lý bình thường. Nếu control đã sai hoặc lỗi provider, verdict của lượt payload sẽ khó diễn giải.

Một manifest thí nghiệm có thể ghi các trường sau. Đây là quy ước tài liệu, không phải dữ liệu của một lượt chạy đã thực hiện:

| Trường cần lưu | Vai trò trong phân tích |
|---|---|
| `source_event_id`, `request_timestamp` | Nối sự kiện gốc với log/alert |
| `model`, `profile`, `memory_state` | Mô tả điều kiện có thể ảnh hưởng đầu ra |
| `control_case`, `treatment_case` | Ghi rõ biến được thay đổi |
| `context_provenance` | Xác nhận mô hình thực sự tiếp xúc dữ liệu |
| `verdict`, `evidence_status` | Tách đánh giá hành vi với độ đầy đủ bằng chứng |

Việc khôi phục hoặc xóa memory là thao tác riêng có thể làm mất lịch sử. Quy trình chuẩn bị thí nghiệm phải xuất dữ liệu cần giữ trước và tuân theo quyền của người vận hành. Lần viết bài này không thực hiện reset hoặc gửi payload lên lab.

## Vì sao giữ response ở dry-run giúp đọc kết quả rõ hơn

Với đề tài sinh viên, nhóm cần quan sát mô hình đề xuất gì trước khi cho phép hệ thống làm thật. Dry-run giúp lưu kế hoạch và xem tác động dự kiến mà không tự biến một verdict thành thay đổi firewall hoặc host.

Đổi lại, dry-run chưa đo được hiệu quả chặn lưu lượng thực. Khi trình bày demo, cần giữ hai kết luận tách biệt: hệ thống có tạo kế hoạch đúng định dạng hay không, và biện pháp đó có chặn hành vi trong môi trường thực thi hay không. Hồ sơ đang có chỉ hỗ trợ kết luận theo từng phép kiểm được ghi nhận.

## Phần còn thiếu để gọi một phép thử là tái hiện được

Trong báo cáo manual lịch sử, URL/run ID chưa được ghi đầy đủ để nối độc lập mọi mắt xích. Luồng runtime có trong code cũng không tự xác nhận toàn bộ tích hợp Red → Wazuh → Blue công khai đã được kiểm chứng ở cùng một đợt.

Một bước tiếp theo có giá trị là chuẩn hóa bản ghi cho mỗi lượt: cùng ID xuyên tầng, snapshot điều kiện model/memory, dữ liệu đối chứng và verdict có provenance. Cần thêm nhiều lần lặp để quan sát độ biến thiên, thay vì chỉ tăng số lượng payload khác nhau.

## Nguồn và điểm đọc tiếp

1. Hồ sơ nhóm: `docs/gate-2/eval-evidences/manual-eval/manual-eval-report.md`, ca E02–E04; có phân biệt PASS giao diện và INCONCLUSIVE khai thác.
2. Kiến trúc và phạm vi: `README.md`, `.agents/REPO_CONTEXT.md`, `docs/architecture.md` trong repo P-070.
3. [OWASP LLM01:2025, Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/).
4. [Hồ sơ dự án P-070 và video của nhóm](/projects/p070-ai-redteam-soc.html).
5. [Nguồn tài sản và hash tài liệu đã đối chiếu](/assets/p070/sources.json).

Đọc tiếp [thí nghiệm RAG poisoning bốn pha](/research/p070-rag-poisoning-four-phase.html) để xem một quy trình đã ghi rõ điều kiện delivery, control và recovery.
