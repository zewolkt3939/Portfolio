## 1. Câu hỏi nghiên cứu

Sau khi đã bảo toàn đầy đủ các sự kiện riêng biệt ở bước [khử trùng lặp cảnh báo](/research/alert-deduplication.html), lớp tiếp theo của một pipeline SOC là **tương quan sự kiện (event correlation)**. Một quy tắc phát hiện brute-force truyền thống thường đếm số lần đăng nhập thất bại từ cùng một địa chỉ IP trong các khung thời gian cố định (fixed tumbling windows, ví dụ mỗi phút từ giây `00` đến `59`). Câu hỏi của ghi chép này là: **vì sao khung thời gian cố định theo từng IP dễ bỏ lọt tấn công nằm vắt qua ranh giới phút hoặc tấn công rải mật khẩu phân tán (password spraying), và việc kết hợp cửa sổ trượt (sliding window) với nhiều chiều thực thể khắc phục nhược điểm đó như thế nào?**

## 2. Thiết kế thí nghiệm

Hàm `correlation_experiment` trong [`run_labs.py`](/research/labs/run_labs.py) phát lại bốn kịch bản sự kiện xác thực thất bại qua hai bộ quy tắc:

- **Nhánh khung cố định theo IP (`fixed_bucket`):** Chia trục thời gian thành từng ô 60 giây cố định (`bucket = t // 60`) và chỉ kích hoạt cảnh báo khi một cặp `(bucket, src_ip)` có từ `5` sự kiện trở lên.
- **Nhánh cửa sổ trượt đa thực thể (`sliding_multi_entity`):** Tại mỗi sự kiện đến ở thời điểm `t_end`, xét cửa sổ trượt `[t_end - 60, t_end]` và kích hoạt cảnh báo nếu **một IP vượt ngưỡng `>= 5` lần thất bại** HOẶC **số tài khoản đích riêng biệt bị thử sai trong cửa sổ đạt `>= 5` tài khoản** (dấu hiệu password spraying).

```python
window = [item for item in events[: i + 1] if t_end - item[0] <= 60]
ip_counts = {}
users = set()
for _t, wip, wuser in window:
    ip_counts[wip] = ip_counts.get(wip, 0) + 1
    users.add(wuser)
if any(c >= 5 for c in ip_counts.values()) or len(users) >= 5:
    sliding_detected = True
```

[![Sơ đồ kiến trúc thu thập, chuẩn hóa và tương quan cảnh báo Wazuh với cơ chế dự phòng tất định.](/assets/research/wazuh-triage-arch.svg)](/assets/research/wazuh-triage-arch.svg)

Hình 1. Vị trí của bước tương quan sự kiện trong kiến trúc xử lý cảnh báo có hỗ trợ AI và cơ chế dự phòng heuristic.

Bốn kịch bản kiểm thử gồm:

1. **`single-IP burst (6 fails in 12s)`:** Một IP thử sai 6 lần lên tài khoản `alice` từ giây `10` đến giây `20`.
2. **`boundary-split burst (3 at 58s, 3 at 62s)`:** Cùng một IP thử sai 6 lần chỉ trong 6 giây (`t = 57..63`), nhưng nằm vắt qua ranh giới phút thứ nhất và phút thứ hai.
3. **`distributed spray (6 IPs -> 6 users in 15s)`:** Sáu địa chỉ IP khác nhau thử mật khẩu phổ biến lên sáu tài khoản khác nhau trong 15 giây (mỗi IP chỉ xuất hiện 1 lần).
4. **`normal typo (2 fails by 1 user)`:** Người dùng gõ nhầm mật khẩu 2 lần rồi dừng — ca kiểm thử hồi quy nhằm bảo đảm không sinh cảnh báo giả.

## 3. Kết quả quan sát

[![Bốn kịch bản tương quan log: khung cố định theo IP chỉ đúng 2/4 ca; cửa sổ trượt đa thực thể đúng cả 4/4 ca.](/assets/research/correlation-results.svg)](/assets/research/correlation-results.svg)

Hình 2. Kết quả đối chiếu giữa khung thời gian cố định theo IP và cửa sổ trượt đa thực thể từ [`results.json`](/research/labs/results.json).

Nhánh `fixed_bucket` chỉ xử lý đúng **2/4** kịch bản:

- Ở kịch bản **`boundary-split burst`**, dù 6 lần thử sai diễn ra trong vòng 6 giây, việc chia ô tại mốc `t = 60` tách chuỗi sự kiện thành hai ô có giá trị `3` và `3` (đều dưới ngưỡng `5`), dẫn đến bỏ lọt hoàn toàn.
- Ở kịch bản **`distributed spray`**, mỗi IP nguồn chỉ gửi đúng 1 yêu cầu nên bộ đếm theo `src_ip` luôn bằng `1`, không bao giờ chạm ngưỡng.

Nhánh `sliding_multi_entity` xử lý đúng cả **4/4** kịch bản: phát hiện được cả chuỗi sự kiện vắt qua biên phút lẫn đợt password spraying phân tán, đồng thời giữ yên lặng trước trường hợp gõ nhầm thông thường (`normal typo`).

## 4. Đánh đổi kỹ thuật khi triển khai thực tế

- **Chi phí bộ nhớ của cửa sổ trượt:** Khung cố định (`tumbling window`) chỉ cần giữ một bộ đếm số nguyên cho mỗi khóa rồi xóa sạch khi sang phút mới. Cửa sổ trượt chính xác cần lưu danh sách mốc thời gian hoặc xấp xỉ bằng *sliding window counter* (kết hợp trọng số của ô hiện tại và ô liền trước) để giới hạn RAM.
- **Nguy cơ nhiễu trên hệ thống đăng nhập lớn:** Đếm số lượng tài khoản riêng biệt (`distinct users`) trên toàn dịch vụ rất nhạy với password spraying, nhưng vào giờ cao điểm buổi sáng khi nhiều nhân viên cùng đăng nhập sai một lần, ngưỡng tĩnh có thể gây false positive. Trong vận hành thực tế, mình có thể kết hợp thêm điều kiện như cùng `User-Agent`, cùng ASN, hoặc cùng mã lỗi xác thực.

## 5. Tái lập thí nghiệm

```powershell
python research/labs/run_labs.py
python tools/render_lab_figures.py
```

[Tải mã nguồn lab ↓](/research/labs/run_labs.py)[Xem kết quả JSON ↗](/research/labs/results.json)[Xem bài Khử trùng lặp cảnh báo ↗](/research/alert-deduplication.html)[Tải biểu đồ SVG ↓](/assets/research/correlation-results.svg)

## Tài liệu tham khảo

1. MITRE ATT&CK. [T1110.003 — Brute Force: Password Spraying](https://attack.mitre.org/techniques/T1110/003/). Đặc trưng hành vi thử một mật khẩu trên nhiều tài khoản để tránh khóa tài khoản và ngưỡng theo IP.
2. Wazuh Documentation. [Correlation rules and frequency/timeframe options](https://documentation.wazuh.com/current/user-manual/ruleset/ruleset-xml-syntax/rules.html). Cách cấu hình `frequency`, `timeframe` và `same_source_ip` / `same_user`.
3. Portfolio case study. [AI-powered alert prioritization for Wazuh](/projects/ai-wazuh-triage.html).
