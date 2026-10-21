## 1. Câu hỏi nghiên cứu

Trong các bản dựng hệ điều hành nhúng như Yocto / OpenEmbedded hoặc các bản phân phối Linux ổn định, việc khắc phục lỗ hổng bảo mật thường được thực hiện bằng cách **backport bản vá (patch)** trực tiếp vào recipe thay vì nâng cấp toàn bộ gói lên phiên bản upstream mới. Điều này đặt ra một vấn đề thực tế cho quy trình quản lý lỗ hổng chuỗi cung ứng (SCA/SBOM): **nếu công cụ quét chỉ đối sánh chuỗi phiên bản (CPE version matching), tỷ lệ cảnh báo giả và điểm mù sẽ xuất hiện ở đâu?**

Ghi chép này mô hình hóa bài toán phân loại CVE bằng một thí nghiệm nhỏ có thể tái lập, lấy cảm hứng từ quá trình mình thực hiện [dự án OSSVS trên webOS OSE](/projects/ossvs-supply-chain.html), nhưng sử dụng dữ liệu tổng hợp hoàn toàn độc lập.

## 2. Thiết kế thí nghiệm

Hàm `sbom_experiment` trong [`run_labs.py`](/research/labs/run_labs.py) xây dựng sáu bản ghi thành phần phần mềm đại diện cho các tình huống thực tế trong một bản dựng Linux nhúng:

1. **`curl (7.82.0)` — Gói có lỗ hổng chưa vá và nằm trong image đích:** Cần phải vá (`patch required`).
2. **`openssl (3.0.7)` — Đã áp dụng bản vá CVE trong recipe nhưng giữ nguyên chuỗi phiên bản `3.0.7`:** Đã được giảm thiểu bởi backport (`mitigated by backport`).
3. **`cmake-native (3.24.2)` — Công cụ chỉ chạy trên máy host lúc biên dịch, không đóng gói vào rootfs đích:** Không hiện diện trên thiết bị (`not in target rootfs`).
4. **`libxml2 (2.9.14)` — Có bản vá mục tiêu đã kiểm chứng trong quy trình build:** Đã được giảm thiểu bởi backport (`mitigated by backport`).
5. **`custom-ipc (unknown)` — Thành phần nội bộ thiếu thông tin phiên bản trong SBOM:** Không thể kết luận an toàn tự động, cần rà soát thủ công (`manual audit required`).
6. **`zlib (1.3.1)` — Đã ở phiên bản upstream an toàn:** Không bị ảnh hưởng (`clean`).

```python
version_only = "patch required" if item["cve_version_match"] else "clean"

if not item["version"]:
    context_decision = "manual audit required"
elif not item["reachable_in_image"]:
    context_decision = "not in target rootfs"
elif item["cve_version_match"] and item["backport_patch"]:
    context_decision = "mitigated by backport"
elif item["cve_version_match"]:
    context_decision = "patch required"
else:
    context_decision = "clean"
```

## 3. Kết quả quan sát

[![Sáu bản ghi thành phần phần mềm: quét theo phiên bản chỉ khớp 2/6 quyết định thực tế; phân loại theo ngữ cảnh build và bản vá khớp 6/6.](/assets/research/sbom-results.svg)](/assets/research/sbom-results.svg)

Hình 1. So sánh quyết định của phương pháp chỉ dựa vào chuỗi phiên bản và phương pháp kết hợp metadata bản vá từ [`results.json`](/research/labs/results.json).

Phương pháp chỉ dựa vào chuỗi phiên bản (`version_only`) chỉ đưa ra quyết định khớp với trạng thái thực tế ở **2/6** trường hợp (`curl 7.82.0` và `zlib 1.3.1`):

- **Cảnh báo giả (False Positives):** Cả `openssl (3.0.7)`, `libxml2 (2.9.14)` (đã có patch trong recipe) và `cmake-native (3.24.2)` (không nằm trong rootfs của thiết bị) đều bị gắn nhãn phải vá khẩn cấp chỉ vì chuỗi phiên bản nằm trong khoảng bị ảnh hưởng của CVE.
- **Điểm mù (False Negative / Silent Skip):** Gói `custom-ipc` bị thiếu chuỗi phiên bản nên không khớp với bất kỳ biểu thức CPE nào; bộ quét đơn giản coi nó là `clean` thay vì báo hiệu khoảng trống dữ liệu cần kiểm tra.

Khi bổ sung ba thuộc tính ngữ cảnh — **tính đầy đủ của phiên bản**, **sự hiện diện trong target image** và **metadata bản vá backport** — nhánh `context_triage` đưa ra quyết định chính xác cho cả **6/6** trường hợp.

## 4. Ý nghĩa đối với quy trình SBOM và VEX

Trong thực tế vận hành bảo mật chuỗi cung ứng:

- **Báo cáo cả tử số và mẫu số của độ bao phủ định danh:** Một bản kiểm kê có 99,4% gói xác định được phiên bản đồng nghĩa với việc 0,6% gói còn lại đang đứng ngoài khả năng tự động đối sánh CVE. Các gói `unknown` phải được tách thành hàng đợi kiểm tra riêng.
- **Lưu trữ bằng chứng bản vá (Patch Provenance / VEX):** Khi áp dụng backport mà không tăng số phiên bản upstream, danh sách file `.patch` trong recipe và trạng thái build image là nguồn dữ liệu xác thực duy nhất để giải trình vì sao một CVE đã được xử lý (tương ứng với trạng thái `not_affected` / `fixed` trong chuẩn CSAF/VEX).

## 5. Tái lập thí nghiệm

```powershell
python research/labs/run_labs.py
python tools/render_lab_figures.py
```

[Tải mã nguồn lab ↓](/research/labs/run_labs.py)[Xem kết quả JSON ↗](/research/labs/results.json)[Đọc nghiên cứu tình huống OSSVS ↗](/projects/ossvs-supply-chain.html)[Tải biểu đồ SVG ↓](/assets/research/sbom-results.svg)

## Tài liệu tham khảo

1. CISA / NTIA. [Minimum Elements for a Software Bill of Materials (SBOM)](https://www.cisa.gov/sbom). Khung dữ liệu định danh thành phần và khả năng khai thác (VEX).
2. Yocto Project. [Checking for Vulnerabilities (cve-check)](https://docs.yoctoproject.org/singleindex.html#checking-for-vulnerabilities). Cơ chế theo dõi `CVE_STATUS` và các bản vá `.patch` trong recipe OpenEmbedded.
3. Portfolio case study. [OSSVS: supply-chain vulnerability management](/projects/ossvs-supply-chain.html). Bối cảnh thực tế của bài toán phân loại CVE trên webOS OSE.
