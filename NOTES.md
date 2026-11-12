# Phân tích kết quả · Day 04

- Họ và tên: Mai Văn Thanh
- MSSV: 2A202603696
- Lớp: L3A

Hai bộ hoàn tất ngày 12/11/2026, mỗi bộ đủ 22 case. Cùng Groq `openai/gpt-oss-20b` cho agent và judge, dataset `core`, snapshot 09/11/2026, `max_steps=8`, khoảng cách request tối thiểu 3,2 giây.

## 1. Case được chọn

**E4:** Xem incident GitHub xr3myzj7ms51: những component được ghi nhận nào bị ảnh hưởng? Actions có liên quan không?

Baseline đã đọc incident nhưng answer không có URL tool trả về, thay bằng ký hiệu giống lời gọi tool:

~~~text
| **Actions** | The incident update notes that “Actions workflow runs and job status updates were delayed by up to 25 minutes”【commentary to=functions.get_incident_details <|constrain|>json:{"incident_id":"xr3myzj7ms51","provider":"github"}】 |
~~~

Judge vẫn cho 100/100. Nguyên nhân có thể xảy ra: prompt yêu cầu dẫn nguồn nhưng loop chưa kiểm tra URL trước khi chấp nhận `stop`. Cải tiến bổ sung kiểm tra trong loop để phát hiện lỗi này.

## 2. Bằng chứng trong trace

Trích tool call của E4 baseline, lược nội dung incident:

~~~json
{
  "event": "tool",
  "step": 1,
  "name": "get_incident_details",
  "arguments": {
    "incident_id": "xr3myzj7ms51",
    "provider": "github"
  },
  "result": {
    "ok": true,
    "provider": "github",
    "url": "https://stspg.io/pjgptg3cfc6n"
  }
}
~~~

E4 improved có URL trên, vẫn đạt 100/100 và không có event sửa nguồn: model đã tự dẫn URL. Bằng chứng có lượt sửa thực sự nằm ở **E5**: đọc incident trả URL `https://stspg.io/hj74883wgn0t`, step 3 thiếu URL, step 4 trả answer có URL đó:

~~~json
[
  {
    "event": "model",
    "step": 3,
    "finish": "stop"
  },
  {
    "event": "validation_missing_source",
    "step": 3
  },
  {
    "event": "model",
    "step": 4,
    "finish": "stop"
  }
]
~~~

Bản improved ghi nhận 3 event `validation_missing_source`: E2 step 3, E5 step 3 và H6 step 4. Toàn bộ answer, tool results và usage nằm trong hai file eval.

## 3. Thay đổi

- Hoàn thiện ReAct thủ công: giữ nguyên assistant message, parse JSON arguments, xử lý mọi tool call và trả kết quả đúng `tool_call_id`.
- JSON lỗi trả `INVALID_ARGUMENTS`; lỗi tool trở thành observation. Lỗi provider hoặc finish bất thường trả `error`; hết lượt trả `max_steps`.
- Lưu URL từ `get_incident_details` thành công. Khi answer thiếu tất cả URL đã quan sát, ghi event và yêu cầu sửa trong cùng ngân sách bước. Không bắt URL nếu chưa đọc incident thành công.
- `--baseline` chỉ tắt kiểm tra URL; hai bộ dùng chung prompt, tools và xử lý lỗi. Adapter Groq, checkpoint/resume và điều tiết request dùng chung.

## 4. So sánh kết quả

| Chỉ số | Trước | Sau |
|---|---:|---:|
| Case đã chấm | 22/22 | 22/22 |
| Điểm /100 | 86.73 | 89.00 |
| Lượt agent có usage | 65 | 67 |
| Lượt judge có usage | 21 | 21 |
| Tổng token agent + judge đã lưu | 130110 | 139319 |
| Answer completed có URL / số completed đã đọc incident | 7/11 | 12/12 |
| Event thiếu nguồn | 0 | 3 |

Điểm tổng tăng **2,27 điểm**. Groq không trả trường cost, nên chưa có số liệu chi phí. Kiểm tra offline đạt 37 tests gốc và 3 tests agent bonus; chưa chạy 10 case eval bonus.

| Case tiêu biểu | Trước | Sau |
|---|---:|---:|
| E4 | 100 | 100 |
| E5 | 91 | 95 |
| A1 | 0 | 0 |
| A5 | 92 | 25 |
| H6 | 85 | 96 |
| H7 | 58 | 63 |

- **E4:** khắc phục thiếu URL trong answer, dù judge không phản ánh lỗi ở điểm số.
- **E5, H6:** có lượt sửa nguồn thực sự. Số lượt/token còn phụ thuộc cách model chọn tools, không chỉ riêng kiểm tra URL.
- **A1:** cả hai hết 8 lượt trước khi có answer; kiểm tra nguồn chưa sửa chiến lược đọc quá nhiều incident.
- **A5:** bản sau ghi năm 2025 nhưng liệt kê incident năm 2026; lỗi thời gian chưa được kiểm tra.
- **H7:** cả hai khẳng định Cloudflare operational dù tool timeout; không có incident đọc thành công nên kiểm tra URL không can thiệp.

## 5. Giới hạn

- Có URL đúng không chứng minh mọi nhận định đúng. E2 improved còn suy đoán ảnh hưởng gián tiếp tới khách hàng không FedRAMP dù tool nói nhóm này không bị ảnh hưởng; judge vẫn cho 100.
- So URL bằng chuỗi chưa nhận diện URL tương đương hoặc giải shortlink. Snapshot là dữ liệu lịch sử; tools chỉ tìm trong 50 incident và lược bớt updates.
- Mỗi phiên bản chạy một lần, cùng model làm agent và judge; không quy toàn bộ chênh lệch điểm cho cải tiến hoặc đổi điểm eval thành điểm rubric.
- Eval được resume sau lỗi quota; H6–H8 baseline từng được chạy bổ sung cùng cấu hình sau khi file quay về checkpoint 19 case. Usage chỉ tính các lượt hiện được lưu, không bao gồm đầy đủ lần thử/lỗi cũ.
- Hướng cải tiến tiếp theo: phân bổ lượt đọc theo ngân sách, kiểm tra năm và phạm vi ảnh hưởng, tách lỗi truy cập khỏi trạng thái dịch vụ.
