# Ghi chú phân tích · Day 04

Họ và tên: Mai Văn Thanh
MSSV: 2A202603696

Thí nghiệm hiện tại dùng Groq. Kết quả của Gemini, OpenRouter hoặc BytePlus không được trộn vào hai bộ này. Các mục chưa có dữ liệu được ghi rõ.

File baseline từng quay về checkpoint 19 case sau khi đã hoàn tất. H6–H8 được bổ sung bằng lượt chạy thật cùng cấu hình, giữ nguyên 19 case trước; không dựng lại điểm/trace từ log. Bản checkpoint tạm ngoài OneDrive được dùng để bảo toàn dữ liệu. Các số liệu dưới đây chỉ tính báo cáo hiện được lưu.

## 1. Case được chọn

- ID hiện chọn: **E4**.
- Câu hỏi: Xem incident GitHub xr3myzj7ms51: những component được ghi nhận nào bị ảnh hưởng? Actions có liên quan không?
- Provider/model: `groq` / `openai/gpt-oss-20b`; judge cùng cấu hình.
- Dataset: core; max steps: 8; request interval tối thiểu: 3.2 giây, thêm thời gian chờ token theo header Groq.
- Điểm baseline: **100**; điểm improved: **100**.
- Baseline đã đọc chi tiết incident thành công nhưng answer không chứa URL tool đã trả về. Đây là lỗi kiểm tra nguồn mà gate xử lý.
- Trích đầu answer baseline thật; toàn văn nằm trong `cases[id=E4].result.answer`:

~~~text
**Incident ID:** xr3myzj7ms51
**Provider:** GitHub

| Component | Evidence of impact |
|-----------|--------------------|
| **Actions** | The incident update notes that “Actions workflow runs and job status updates were delayed by up to 25 minutes”【commentary to=functions.get_incident_details <|constrain|>json:{"incident_id":"xr3myzj7ms51","provider":"github"}】 |
| **Pages** | “Pages deployments dropped to about 4 % of normal volume”【commentary to=functions.get_incident_details <|constrain|>json:{"incident_id":"xr3myzj7ms51","provider":"github"}】 |
| **Webhooks** | “Webhook deliveries dropped to about 58 % of normal volume”【commentary to=functions.get_incident_details json:{"incident_id":"xr3myzj7ms51","provider":"github"}】 |

**Conclusion**

- The incident explicitly recorded **Webhooks, Actions, and Pages** as affected components.
- Actions were indeed related to the incident, with delayed workflow runs and job status updates reported.
- No other components (e.g., Code Scanning, Copilot) were listed as affected in this particular incident.
~~~

## 2. Bằng chứng trong trace

Trích trace baseline thật, giữ các trường cần đối chiếu; toàn bộ result nằm trong file JSON gốc:

~~~json
[
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
      "status": "resolved",
      "url": "https://stspg.io/pjgptg3cfc6n"
    }
  }
]
~~~

- URL đã quan sát xuất hiện trong answer baseline: **False**.
- URL đã quan sát xuất hiện trong answer improved: **True**.
- Event sửa nguồn ở improved của case này: **0**.
- Không coi tên tool hoặc URL do model tự bịa là bằng chứng đã đọc nguồn. Đối chiếu chính URL trả về từ lần `get_incident_details` có `ok: true`.

## 3. Thay đổi đã thực hiện

1. Hoàn thiện vòng ReAct thủ công: append nguyên assistant message, xử lý tất cả calls, ghép đúng tool ID, trả lỗi arguments/tool về model, giới hạn lượt và ghi trace/usage.
2. Bản cải tiến lưu URL từ `get_incident_details` thành công và kiểm tra answer trước khi trả `completed`.
3. Nếu thiếu nguồn, ghi `validation_missing_source`, thêm yêu cầu sửa và tiếp tục trong `max_steps`. Hết lượt trả `max_steps`; không tự tăng ngân sách.
4. Không bắt URL khi chưa đọc incident thành công hoặc tool lỗi.
5. `--baseline` chỉ tắt gate nguồn; bản mặc định bật. Cùng prompt, tools, model/judge, snapshot, dataset và giới hạn bước.

Hỗ trợ vận hành dùng chung: adapter Groq tại `https://api.groq.com/openai/v1/chat/completions`, `GROQ_API_KEY`, tối đa 4096 completion token/request, User-Agent nhận diện ứng dụng, nạp `.env`, checkpoint và resume. Groq chờ token bucket theo `x-ratelimit-reset-tokens`; không retry API ngầm. Lỗi provider vẫn kết thúc run.

Giữ nguyên fixtures, cases, scenarios, grading và tests gốc. Các file debug được thêm trước đây đã được dọn; chỉ giữ mã hỗ trợ trong file gốc.

## 4. So sánh hai lần chạy

| Chỉ số | eval_before.json | eval_after.json |
|---|---|---|
| Điểm toàn bộ | 86.73 | Chưa có điểm tổng (13/22 đã chấm) |
| Điểm E4 | 100 | 100 |
| Lượt agent có usage | 65 | 41 |
| Lượt judge có usage | 21 | 12 |
| Tổng token agent + judge đã lưu | 130110 | 77356 |
| Cost provider báo | Provider không trả trường cost | Provider không trả trường cost |
| Tổng event thiếu nguồn | 0 | 2 |
| Case hết max_steps | 1 | 1 |

37 tests gốc và 3 tests agent bonus đều đạt. Kiểm tra adapter Groq và thời gian chờ token bằng mock cũng đạt, không tiêu tốn API trong kiểm tra offline.

Chỉ so sánh điểm cuối khi mỗi bộ đủ 22 case được chấm, `progress.complete=true` và `summary.score_0_100` khác null. Nếu chưa đủ, không dùng partial mean làm điểm cả bộ. Nếu điểm không tăng hoặc gate không được kích hoạt, phải ghi đúng dữ liệu đó.

## 5. Giới hạn

- Lượt tiếp tục ngày 11/11/2026 đã chấm A6 đạt 95 và A7 đạt 100, nâng bộ improved lên 13/22 case. A8 gặp HTTP 429 ngay lượt model đầu tiên: TPD limit 200.000, used 199.768, requested 536, retry_after 132 giây. Đã dừng gọi API và giữ checkpoint. Thời gian retry chỉ áp dụng cho yêu cầu bị từ chối, không bảo đảm đủ token chạy hết chín case còn lại.

- Các chỉ số usage chỉ tính trace/case hiện được lưu. Lượt gọi lỗi hoặc lần thử cũ bị thay thế khi resume có thể không được tính đầy đủ; không coi đây là hóa đơn độc lập.
- Groq có hạn mức request/token theo phút/ngày; chờ token theo response giảm lỗi tạm thời nhưng không tăng quota ngày hoặc quyền tài khoản.
- Gate chỉ kiểm tra ít nhất một URL đã quan sát xuất hiện trong answer, không chứng minh mọi claim đều được nguồn hỗ trợ; việc so chuỗi chưa nhận diện URL tương đương hoặc giải shortlink.
- Baseline A1 đã dùng đủ 8 lượt gọi tools rồi hết ngân sách trước khi có câu trả lời; grader tính 0. Gate nguồn không trực tiếp sửa chiến lược đọc quá nhiều incident này.
- Gate nguồn không trực tiếp kiểm tra tính đúng của mọi kết luận khi một provider timeout. Phải đối chiếu cả tool error và answer ở các case thiếu dữ liệu.
- Judge là phép đánh giá xấp xỉ, có thể bỏ sót lỗi. Cần đọc answer và trace, kể cả khi điểm cao.
- Snapshot bài chính ngày 09/11/2026 là dữ liệu lịch sử; tools chỉ tìm trong 50 incident và trả một phần updates.
- Một lần chạy mỗi phiên bản chưa chứng minh độ ổn định; không tự quy điểm eval thành điểm rubric hoặc cộng bonus khi chưa chạy đủ bộ tương ứng.
