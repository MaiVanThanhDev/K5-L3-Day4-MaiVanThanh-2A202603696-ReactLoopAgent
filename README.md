# Status Investigation Agent · Day 04

- Họ và tên: Mai Văn Thanh
- MSSV: 2A202603696
- Lớp: L3A

Agent ReAct bằng Python dùng tools để kiểm tra trạng thái GitHub và Cloudflare. Model đề xuất tool call, Python thực thi và trả kết quả về model. Bản cải tiến kiểm tra URL nguồn trước khi trả câu trả lời.

## Chạy chương trình

Yêu cầu Python 3.10 trở lên, không cần cài thêm package. Mở terminal trong thư mục chứa `run.py`:

```powershell
python run.py --env-file .env "Theo snapshot, GitHub Actions có sự cố gì?"
```

Cấu hình hiện tại dùng Groq, model `openai/gpt-oss-20b` cho cả agent và judge. File `.env` trên máy đã có key. Khi cài trên máy khác, tạo `.env` theo [.env.example](.env.example) và điền `GROQ_API_KEY`. Giữ key thật trong `.env`, không đưa vào Git.

Chế độ mặc định đọc snapshot ngày 09/11/2026; lời gọi model vẫn dùng API. Trong kết quả JSON, `answer` là câu trả lời, `trace` là các lượt model/tool và `usage` là token provider báo.

## Kiểm tra offline

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s bonus -p "test_*.py" -v
```

Kết quả: 37 tests gốc và 3 tests agent bonus đều đạt.

## Kết quả eval

| Báo cáo | Case đã chấm | Điểm /100 |
|---|---:|---:|
| [eval_before.json](eval_before.json) | 22/22 | 86.73 |
| [eval_after.json](eval_after.json) | 22/22 | 89.00 |

Hai bộ cùng cấu hình, dataset core và `max_steps=8`. Baseline tắt riêng kiểm tra URL nguồn; bản sau bật. Phân tích bằng chứng, token và lỗi còn lại nằm trong [NOTES.md](NOTES.md). Điểm eval là tham khảo; bộ 10 case bonus chưa chạy.

## Tái lập eval

Các lệnh sau gọi API và ghi lại báo cáo:

```powershell
python evals/run_evals.py --env-file .env --baseline --output eval_before.json
python evals/run_evals.py --env-file .env --output eval_after.json
```

Nếu bị gián đoạn, thêm `--resume` vào đúng lệnh để giữ các case đã chấm. Khi gặp HTTP 429, chờ quota phục hồi rồi tiếp tục.

## Bài nộp

Tên repo theo lớp L3A: `K5-L3A-DAY04-MaiVanThanh-2A202603696-ReactLoopAgent`.

Các file chính: `agent.py`, `eval_before.json`, `eval_after.json`, `NOTES.md`; giữ các file đề còn lại. Đổi tên repo tại GitHub → Settings → General → Repository name, push thay đổi và nộp link repo public lên LMS theo [SUBMISSION.md](SUBMISSION.md).

Tài liệu đề: [GUIDE.md](GUIDE.md) · [RUBRIC.md](RUBRIC.md) · [SUBMISSION.md](SUBMISSION.md).
