## 1. Câu hỏi nghiên cứu

Khi kiểm thử một rule firewall trên Linux, việc gửi gói tin tấn công và thấy ứng dụng đích không nhận được gói tin mới chỉ chứng minh **lưu lượng không đi tới đích**, chưa chứng minh **rule đang kiểm thử đã chặn gói tin đó và ghi lại bằng chứng**. Trên thực tế, cơ chế lọc đường ngược của kernel (`rp_filter`) hoặc các hook sớm trong Netfilter có thể loại bỏ gói tin giả mạo trước khi nó chạm tới chain `filter/INPUT`. Câu hỏi của ghi chép này là: **đặt điểm thu thập telemetry `NFLOG` ở đâu để vừa chặn đúng gói tin không hợp lệ, vừa không để mất dấu vết của các gói tin giả mạo (spoofed packets)?**

Bài viết này mô hình hóa bài toán thứ tự hook mà mình đã gặp trong kỳ thực tập [Embedded Linux security & observability](/projects/lg-embedded-security.html), dưới dạng một mô phỏng tất định có thể chạy độc lập bằng Python.

## 2. Thiết kế thí nghiệm

Hàm `netfilter_experiment` trong [`run_labs.py`](/research/labs/run_labs.py) khảo sát sáu mẫu gói tin đi qua hai kiến trúc ghi log khác nhau:

- **Kiến trúc A (`input_only_evidence`):** Kernel bật kiểm tra tính hợp lệ nguồn sớm (tương đương `rp_filter` hoặc drop sớm), nhưng rule xuất log `NFLOG` chỉ đặt tại `filter/INPUT`.
- **Kiến trúc B (`dual_hook_evidence`):** Đặt rule nhận diện và ghi nhận gói giả mạo ngay tại `mangle/PREROUTING` (xuất ra nhóm `nflog-prerouting`), đồng thời giữ rule kiểm soát chính sách và nhóm `nflog-input` tại `filter/INPUT`.

[![Sơ đồ kiến trúc kiểm thử Netfilter và thu thập telemetry qua hai nhóm NFLOG trên webOS OSE.](/assets/research/lg-netfilter-arch.svg)](/assets/research/lg-netfilter-arch.svg)

Hình 1. Sơ đồ đường đi gói tin qua `mangle/PREROUTING`, `filter/INPUT` và hai nhánh `ulogd2` xuất đồng thời log văn bản và JSON.

Sáu mẫu gói tin trong bộ fixture gồm:

1. **`whitelisted IPv4 unicast` (`192.168.10.5 -> 192.168.10.1`, `TCP/443`):** Lưu lượng hợp lệ trong danh sách cho phép.
2. **`LAND spoof (src == dst)` (`192.168.10.1 -> 192.168.10.1`, `TCP/80`):** Gói tin giả mạo địa chỉ nguồn trùng địa chỉ đích.
3. **`RFC1918 martian source` (`127.0.0.5 -> 192.168.10.1`, `UDP/53`):** Gói tin có nguồn loopback đến từ giao diện mạng vật lý.
4. **`unlisted IPv4 source` (`192.168.10.99 -> 192.168.10.1`, `TCP/22`):** Nguồn hợp lệ về mặt định tuyến nhưng không nằm trong whitelist dịch vụ.
5. **`approved IPv6 multicast` (`fe80::10 -> ff02::1:ff00:1`, `ICMPv6`):** Gói multicast thuộc nhóm được phép.
6. **`unapproved multicast group` (`fe80::10 -> ff05::99`, `UDP/1900`):** Gói multicast gửi tới nhóm không được phê duyệt.

## 3. Kết quả quan sát

[![Sáu mẫu gói tin qua Netfilter: chỉ đặt log ở INPUT làm mất dấu 2/4 gói bị chặn; đặt log ở cả PREROUTING và INPUT ghi nhận đủ 4/4.](/assets/research/netfilter-results.svg)](/assets/research/netfilter-results.svg)

Hình 2. Đối chiếu khả năng quan sát các gói bị chặn giữa thiết kế chỉ ghi log ở `INPUT` và thiết kế ghi log hai tầng (`PREROUTING` + `INPUT`).

Trong bốn gói tin bị từ chối (`total_dropped = 4`):

- Kiến trúc chỉ đặt log tại `INPUT` chỉ ghi nhận được **2/4** trường hợp (`unlisted IPv4 source` và `unapproved multicast group`). Hai gói tin giả mạo (`LAND spoof` và `martian source`) bị rơi vào trạng thái **`silent drop`** — gói bị chặn nhưng bộ đếm rule tại `INPUT` bằng `0` và `ulogd2` không có bản ghi JSON nào.
- Kiến trúc hai tầng (`dual_hook_evidence`) ghi nhận đủ **4/4** gói bị từ chối, đồng thời phân biệt rõ nguyên nhân: gói bị loại ở lớp kiểm tra giả mạo sớm (`nflog-prerouting`) hay bị loại ở lớp chính sách dịch vụ (`nflog-input`).

## 4. Ý nghĩa khi vận hành ulogd2 và kiểm chứng firewall

1. **Bộ đếm bằng 0 không phải lúc nào cũng là lỗi công cụ tạo gói:** Khi dùng Scapy bắn lưu lượng thử nghiệm mà bộ đếm ở `filter/INPUT` không tăng, câu hỏi đầu tiên cần đặt ra là gói tin đã bị loại ở `PREROUTING` / routing decision hay chưa.
2. **Tách nhóm NFLOG cho các luồng đầu ra song song:** Trong thực tế triển khai `ulogd2`, hai stack ghi log (ví dụ một stack xuất LOGEMU dạng dòng văn bản và một stack xuất JSON) không thể cùng bind vào một `nlgroup`. Quy ước tách nhóm (chẳng hạn `JSON = TEXT + 100`) giúp hai luồng thu thập hoạt động độc lập mà không tranh chấp socket Netlink.

## 5. Tái lập thí nghiệm

```powershell
python research/labs/run_labs.py
python tools/render_lab_figures.py
```

[Tải mã nguồn lab ↓](/research/labs/run_labs.py)[Xem kết quả JSON ↗](/research/labs/results.json)[Đọc nghiên cứu tình huống LG lab ↗](/projects/lg-embedded-security.html)[Tải biểu đồ SVG ↓](/assets/research/netfilter-results.svg)

## Tài liệu tham khảo

1. Netfilter Project. [nftables / Netfilter hooks architecture](https://wiki.nftables.org/wiki-nftables/index.php/Netfilter_hooks). Thứ tự các hook `ingress`, `prerouting`, `input`, `forward`, `output`, `postrouting`.
2. Linux Kernel Documentation. [IP Sysctl — rp_filter](https://docs.kernel.org/networking/ip-sysctl.html). Cơ chế kiểm tra đường ngược và xử lý địa chỉ martian.
3. Portfolio case study. [Embedded Linux security & observability](/projects/lg-embedded-security.html). Thực nghiệm kiểm chứng Netfilter và ulogd2 trên webOS OSE.
