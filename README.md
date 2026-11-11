# Lab: Xây dựng Status Investigation Agent

> **Hình thức: Bài cá nhân.** Mỗi cá nhân tự làm, tự tạo repo riêng và tự nộp link lên LMS.
>
> **Tên repo nộp:** `K5-L3A-DAY04-[HoVaTen]-[MSSV]-ReactLoopAgent` hoặc `K5-L3B-DAY04-[HoVaTen]-[MSSV]-ReactLoopAgent` (thay `[HoVaTen]` và `[MSSV]`, bỏ cả dấu ngoặc vuông) · **Nơi nộp:** [aithucchien.vinuni.edu.vn](https://aithucchien.vinuni.edu.vn)
>
> **Deadline (GMT+7):** ca 9:00–13:00 và 14:00–18:00 trước 23:59 cùng ngày, ca 16:30–20:00 trước 12:00 trưa hôm sau. Nộp muộn bị trừ điểm.

Tài liệu đi kèm: [GUIDE.md](GUIDE.md) · [SUBMISSION.md](SUBMISSION.md) · [RUBRIC.md](RUBRIC.md) · [CHECKPOINTS.md](CHECKPOINTS.md) · [RULES.md](RULES.md)

Bạn sẽ tự viết một agent loop bằng Python. Agent dùng dữ liệu thật từ GitHub Status và Cloudflare Status để hỗ trợ điều tra sự cố, sau đó bạn dùng trace và eval để kiểm tra cách agent hoạt động.

**Mục tiêu:** gọi LLM → thực thi tool → đưa kết quả trở lại LLM → lặp đến khi trả lời hoặc hết giới hạn. Thời lượng dự kiến: **4 giờ**, gồm nghỉ 10 phút. Lịch theo từng ca ở [CHECKPOINTS.md](CHECKPOINTS.md). Toàn bộ các bước trong [GUIDE.md](GUIDE.md) là nội dung của lab. Đọc thêm [RUBRIC.md](RUBRIC.md) để biết tiêu chí đánh giá.

## Agent hoạt động như thế nào?

Sơ đồ dưới đây mô tả bài chính với hai tools; phần bonus dùng bộ tools riêng. Agent nhận câu hỏi cùng system prompt và lịch sử hội thoại. LLM đề xuất tool call; Python thực thi tool, đưa kết quả về context rồi gọi LLM tiếp. Quá trình dừng khi có câu trả lời, gặp lỗi hoặc hết giới hạn bước.

<img src="assets/agent-architecture.svg" alt="Sơ đồ agent: user, conversation context, LLM, Python agent loop và hai tools truy cập GitHub Status hoặc Cloudflare Status" width="1200">

## Một vòng thực hành

Sau khi xây agent, bạn chạy eval, phân tích kết quả, cải tiến rồi chạy lại cùng bộ eval để so sánh.

<img src="assets/lab-workflow.svg" alt="Vòng lặp: xây agent, chạy eval, phân tích lỗi, cải tiến và quay lại chạy eval" width="1200">

## Lộ trình học

1. Khám phá status tools và tự code agent loop.
2. Thêm xử lý lỗi, giới hạn bước và trace.
3. Chạy bộ eval 22 case và nhận điểm 0–100 cùng giải thích từng case.
4. Phân tích lỗi trong trace; chọn một thay đổi và cải tiến agent.
5. Chạy lại cùng bộ eval một lần, so sánh điểm, lỗi và chi phí.

Các bước trên là một lab thống nhất. Timeline, yêu cầu và tiêu chí hoàn thành được mô tả trong [GUIDE.md](GUIDE.md).

## Thử thách tùy chọn: +15 điểm

Sau bài chính, bạn có thể mở rộng agent để điều tra **GitHub, Cloudflare, Vercel, npm và DigitalOcean** qua 5 status tools và một tool đọc incident theo trang. Bộ bonus có 10 case riêng về dữ liệu dài, nhiều nhà cung cấp, pagination, lỗi định dạng, rate limit và prompt injection. Xem [GUIDE.md](GUIDE.md#thử-thách-bonus-tùy-chọn--15-điểm) để thực hiện.

Điểm bài chính tối đa 85; bonus tối đa 15, tổng tối đa 100. Không cần làm bonus để hoàn thành bài chính.

## 1. Chuẩn bị

- Python **3.10+**, có Internet và API key của **một** trong bảy provider.
- Chọn model có hỗ trợ **tool calling**. API provider/model có thể phát sinh chi phí.
- Không cần cài package: project dùng Python standard library.

Fork repo đề về tài khoản của bạn, đổi tên theo mẫu (chi tiết ở [SUBMISSION.md](SUBMISSION.md)), clone về máy rồi mở terminal tại thư mục đó:

```bash
python3 --version
export PROVIDER=openai
export MODEL='<tên-model-có-tool-calling>'
export OPENAI_API_KEY='<api-key>'
```

Chọn cấu hình khác nếu cần:

| `PROVIDER` | Biến chứa key | `MODEL` |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | Tên model OpenAI bạn được cấp quyền dùng. |
| `gemini` | `GEMINI_API_KEY` | Tên model Gemini hỗ trợ function calling. |
| `anthropic` | `ANTHROPIC_API_KEY` | Tên model Claude hỗ trợ tool use. |
| `openrouter` | `OPENROUTER_API_KEY` | Model ID đầy đủ trên OpenRouter, thường có dạng provider/model. |
| `deepseek` | `DEEPSEEK_API_KEY` | API trực tiếp của DeepSeek; ví dụ `deepseek-flash`. |
| `byteplus` | `ARK_API_KEY` | Model DeepSeek hoặc Endpoint ID được cấp quyền trên BytePlus ModelArk. |
| `groq` | `GROQ_API_KEY` | Cấu hình hiện tại: `openai/gpt-oss-20b`, được phục vụ qua Groq. |

Ví dụ chuyển sang Gemini: `export PROVIDER=gemini`, đặt `GEMINI_API_KEY` và `MODEL` phù hợp. Chọn một provider; chỉ cần key của dịch vụ đó. File `.env.example` chỉ là mẫu: chương trình **chỉ đọc `.env` khi có `--env-file .env`**. Có thể chạy `cp .env.example .env`, điền key rồi chạy `source .env` trong mỗi terminal mới. Trên Windows, dùng Git Bash để chạy đúng các lệnh này, hoặc thay `python3` bằng `python` và đặt biến bằng `$env:TEN_BIEN='gia_tri'` trong PowerShell. Không commit key hay trace chứa dữ liệu nhạy cảm.

Để nạp cấu hình trực tiếp từ file trên Windows hoặc các shell khác, dùng `--env-file .env`. Tùy chọn này ghi đè các biến cấu hình cũ trong terminal cho tiến trình hiện tại; các tham số CLI như `--provider` và `--model` vẫn được ưu tiên hơn file. Dùng cùng file cấu hình cho hai lần eval:

```powershell
python run.py --env-file .env "Check GitHub Actions status in the snapshot."
python evals/run_evals.py --env-file .env --case E2 --output eval_results_e2.json
```

Mẫu `.env.example` hiện dùng Groq: `PROVIDER=groq`, `MODEL=openai/gpt-oss-20b` và `GROQ_API_KEY`. Agent và judge cùng cấu hình này. Giữ cùng cấu hình giữa hai bộ eval.

Adapter dùng Chat Completions cho OpenAI, Gemini compatibility, OpenRouter, DeepSeek, BytePlus ModelArk và Groq; Anthropic dùng Messages API. Adapter phục vụ **tool calling cơ bản**, không bao phủ mọi tính năng đặc thù model như extended thinking. Khi provider từ chối model hoặc hết quota, kiểm tra quyền truy cập, model ID và key. Xem tài liệu: [OpenAI](https://developers.openai.com/api/docs/guides/function-calling), [Gemini](https://ai.google.dev/gemini-api/docs/openai), [Anthropic](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works), [OpenRouter](https://openrouter.ai/docs/guides/features/tool-calling).

## 2. Chạy thử

Sau khi hoàn thiện `agent.py`:

```bash
python3 run.py 'GitHub Actions hiện có sự cố không? Hãy kiểm tra incident gần đây.'
python3 run.py --mode live 'Cloudflare có incident liên quan cache purge không?'
python3 -m unittest discover -s tests -v
python3 evals/run_evals.py --case E2 --output eval_results_e2.json
python3 evals/run_evals.py --output eval_before.json
# Sau khi phân tích và cải tiến agent:
python3 evals/run_evals.py --output eval_after.json
```

- Mặc định là `snapshot`: đọc dữ liệu được lưu sẵn; vẫn cần LLM API key.
- `live`: gọi status API thật, dữ liệu thay đổi và cần Internet. Cloudflare khuyến nghị User-Agent có thông tin liên hệ; giảng viên có thể đặt `export STATUS_USER_AGENT="StatusAgentLab/1.0 (contact: email-lop@example.edu)"` bằng thông tin liên hệ thực của lớp.
- Unit tests dùng fake provider, không cần key. **Ban đầu một số tests thất bại** vì `agent.py` chưa được implement.
- Eval gọi LLM cho agent và LLM judge, tiêu tốn token. Mỗi case có điểm 0–100; điểm tổng là trung bình các case. Nếu có case chưa chấm được, điểm tổng là `null`. Đọc giải thích và trace; điểm judge là ước lượng, cần kiểm tra lại.
- Có thể override bằng `--provider`, `--model`, `--max-steps`. `--max-steps` là số lần gọi model, mặc định 6 với `run.py`, 8 với `evals/run_evals.py` và 16 khi chạy eval bonus.

Snapshot bài chính được lưu ngày 09/11/2026; snapshot của ba API bổ sung được lưu ngày 10/11/2026. Không dùng nó để trả lời tình trạng hiện tại trong thực tế. Khi chạy live, API có thể rate limit, timeout hoặc thay đổi dữ liệu.

## Tài liệu tham khảo: làm việc với coding agent

Các tài liệu dưới đây giúp bạn tham khảo cách tổ chức việc viết code với AI; **không phải task của lab và không cần cài đặt để hoàn thành bài**.

Trong bài lab, *agent loop* là vòng LLM → tool → kết quả. Khi dùng coding agent, một vòng làm việc khác có thể là: mô tả yêu cầu và tiêu chí hoàn thành → agent sửa code → chạy tests/kiểm tra → đọc kết quả và điều chỉnh. “Loop engineering” trong ngữ cảnh này là thiết kế cách cung cấp nhiệm vụ, phản hồi và điều kiện dừng cho quá trình đó.

| Chủ đề | Tài liệu | Bạn sẽ tìm thấy gì? |
|---|---|---|
| Instructions | [Codex: AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) · [Claude Code: project instructions](https://code.claude.com/docs/en/memory) | Cách cung cấp quy ước dự án và lệnh kiểm tra cho coding agent. |
| Skills | [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills) · [Claude Code: Skills](https://code.claude.com/docs/en/skills) | Cách đóng gói một workflow có thể dùng lại, ví dụ review code hoặc debug. |
| Hooks | [Codex: Hooks](https://learn.chatgpt.com/docs/hooks) · [Claude Code: Hooks](https://code.claude.com/docs/en/hooks) | Cách chạy kiểm tra tại các sự kiện như trước/sau tool call hoặc khi agent kết thúc. |
| Workflow | [GitHub Spec Kit](https://github.github.com/spec-kit/quickstart) · [Superpowers](https://github.com/obra/superpowers) | Hai ví dụ workflow: đi từ yêu cầu đến kế hoạch, implementation và kiểm chứng. Superpowers là dự án cộng đồng. |
| Vòng lặp tự động | [Ralph: bài viết gốc](https://ghuntley.com/ralph/) · [Claude Code Ralph Loop plugin](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/ralph-loop/README.md) | Ví dụ cho agent tiếp tục lặp trên một nhiệm vụ; plugin dùng Stop hook và là một implementation riêng của ý tưởng này. |
| Thiết kế môi trường | [OpenAI: Harness engineering](https://openai.com/index/harness-engineering/) | Vai trò của tests, feedback và môi trường khi giao công việc cho coding agent. |

Nếu thử workflow tự động, hãy đặt giới hạn lượt chạy hoặc chi phí, có điều kiện dừng và tự kiểm tra kết quả. Tests pass là bằng chứng hữu ích, nhưng vẫn cần xem code và đối chiếu yêu cầu. Đọc kỹ quyền và hướng dẫn của từng công cụ trước khi cài hoặc chạy plugin/hook.


## Hướng dẫn từng bước trên Windows

Cấu hình hiện tại gọi model GPT-OSS 20B qua Groq. Model ID có tiền tố `openai/` và được gọi bằng key do Groq cấp. Project dùng thư viện chuẩn Python, không cần cài SDK hay framework agent. Bài chính cần hai bộ eval thật, mỗi bộ 22 case; unit tests đạt chưa thay thế được yêu cầu này.

### Bước 1. Mở terminal tại thư mục dự án

Trong VS Code chọn **Terminal → New Terminal**. Thư mục hiện tại phải chứa `run.py`, `agent.py`, `providers.py` và `.env`. Kiểm tra:

```powershell
python --version
Get-Location
```

Cần Python 3.10 trở lên. Không có bước `pip install`.

### Bước 2. Cấu hình Groq

Tạo API key tại [Groq Console](https://console.groq.com/keys). Điền cấu hình sau vào `.env` trên máy, thay chuỗi mẫu bằng key thật rồi nhấn **Ctrl+S**:

```dotenv
PROVIDER=groq
MODEL=openai/gpt-oss-20b
GROQ_API_KEY=YOUR_GROQ_KEY
JUDGE_PROVIDER=groq
JUDGE_MODEL=openai/gpt-oss-20b
```

Chỉ cần sửa giá trị `GROQ_API_KEY` nếu các dòng khác đã đúng. Key phải được tạo ở Groq; key từ BytePlus, Gemini hoặc OpenRouter thuộc dịch vụ khác. Các cấu hình cũ trong `.env` đã được chuyển thành comment để không bị dùng nhầm. Không gửi key vào chat hoặc commit `.env`.

`--env-file .env` đọc cấu hình trước khi chọn provider/model. File ghi đè biến cũ của terminal trong tiến trình Python; tham số CLI như `--model` được ưu tiên hơn file. File `.env.example` chỉ là mẫu, không chép đè lên file đã có key thật.

Adapter dùng `https://api.groq.com/openai/v1/chat/completions`, giữ tool calls và usage theo contract chung, giới hạn `max_completion_tokens` ở 4096 mỗi request cho agent và judge. Request có User-Agent nhận diện ứng dụng. Không cần cài Groq SDK.

Model GPT-OSS 20B hỗ trợ local tool calling; Python trong dự án thực hiện tools và gửi kết quả về model. Xem [model](https://console.groq.com/docs/model/openai/gpt-oss-20b), [tool calling](https://console.groq.com/docs/tool-use) và [API compatibility](https://console.groq.com/docs/openai).

Groq có giới hạn theo request và token, theo phút hoặc ngày. Kiểm tra hạn mức thực tế của tài khoản tại [Limits](https://console.groq.com/settings/limits); không lấy hạn mức model/dịch vụ cũ áp cho Groq.

### Bước 3. Kiểm tra code không dùng API

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s bonus -p "test_*.py" -v
```

Bộ chính có 37 tests gốc, bộ kiểm tra agent bonus có 3 tests. Các tests dùng provider giả và dữ liệu snapshot nên không tốn token API. Giữ nguyên tests của đề.

### Bước 4. Chạy một câu hỏi để xem agent hoạt động

```powershell
python run.py --env-file .env "Theo snapshot, GitHub Actions có sự cố gì? Hãy kiểm tra incident gần đây."
```

Đọc các trường trong JSON:

| Trường | Cách hiểu |
|---|---|
| `config` | Phải hiện provider `groq` và model `openai/gpt-oss-20b`. |
| `status` | `completed`: kết thúc bình thường; `max_steps`: hết lượt; `error`: run bị lỗi. |
| `trace` | Nhật ký model đề xuất và Python thực hiện tools, cùng kết quả và lỗi. |
| `answer` | Câu trả lời cuối; cần đối chiếu với trace và snapshot. |
| `usage` | Token và các trường sử dụng do provider trả về. Không có trường cost không đồng nghĩa miễn phí. |

Mặc định là snapshot: dữ liệu được lưu sẵn, nhưng phần model vẫn cần Internet và API key. Snapshot bài chính ngày 09/11/2026 không chứng minh trạng thái dịch vụ ở thời điểm hiện tại.

### Bước 5. Hiểu vòng lặp để tự giải thích bài

`agent.py` thực hiện các bước:

1. Tạo `messages` gồm system prompt và câu hỏi.
2. Gọi `provider.complete(messages, schemas)` để nhận assistant message, tool calls, lý do dừng và usage.
3. Thêm nguyên assistant message vào lịch sử.
4. Nếu có calls: đọc JSON arguments, thực thi tất cả tools, thêm từng kết quả với đúng `tool_call_id`, rồi gọi model tiếp.
5. Nếu model kết thúc bình thường: kiểm tra nguồn trước khi trả answer.
6. Gặp lỗi provider hoặc output bị cắt thì trả `error`; hết số lượt gọi model thì trả `max_steps`.

| Thành phần | Ý nghĩa |
|---|---|
| `messages` | Lịch sử hội thoại; model chỉ đọc được kết quả tool sau khi Python thêm vào đây. |
| `SCHEMAS` | Mô tả tên và tham số của các công cụ được phép dùng. |
| `tools.execute()` | Python thực thi hàm; model chỉ đề xuất tên và tham số. |
| `json.loads()` | Chuyển JSON arguments thành dictionary. JSON sai hoặc không phải object được trả lại bằng observation `INVALID_ARGUMENTS`. |
| `tool_call_id` | Ghép kết quả với đúng call, kể cả khi một lượt model trả nhiều calls. |
| `trace` | Bằng chứng về hành vi để phân tích lỗi; không phải bản suy nghĩ nội bộ của model. |
| `max_steps` | Giới hạn số lần gọi model, gồm cả lượt sửa câu trả lời. |
| `observed_urls` | URL được trả về từ lần đọc chi tiết incident thành công. |

Lỗi tool được đưa lại cho model để sửa tham số hoặc báo thiếu dữ liệu. Lỗi provider làm run kết thúc vì không thể tiếp tục gọi model.

### Bước 6. Chạy eval trước cải tiến

```powershell
python evals/run_evals.py --env-file .env --baseline --output eval_before.json
```

`--baseline` chạy cùng agent nhưng tắt riêng kiểm tra URL nguồn. Bản này là mốc trước cải tiến, có thể tái lập từ cùng một file code. Bộ chính gồm E1–E6, A1–A8, H1–H8. Mỗi case có thể gọi model nhiều lần cho agent, rồi thêm một lần cho judge; 22 case không có nghĩa chỉ dùng 22 request.

Runner mặc định giãn các request tối thiểu 3.2 giây, lưu checkpoint sau từng case và dừng khi gặp lỗi provider. Với Groq, adapter còn chờ cửa sổ token theo header `x-ratelimit-reset-tokens` trả về sau mỗi response; thời gian chờ thực tế có thể dài hơn 3.2 giây. Đây là điều tiết tốc độ, không phải gọi lại API ngầm. Lỗi provider vẫn kết thúc run.

### Bước 7. Phân tích và hiểu thay đổi kiểm tra nguồn

Bản cải tiến đã có trong `agent.py` và được bật mặc định:

1. Lưu URL khi `get_incident_details` trả `ok: true`.
2. Khi model trả lời xong, kiểm tra answer có ít nhất một URL đã quan sát.
3. Nếu thiếu, ghi event `validation_missing_source`, thêm yêu cầu sửa vào `messages` rồi lặp tiếp.
4. Lượt sửa vẫn tính vào `max_steps`; hết lượt trả `max_steps`.
5. Không ép chèn URL khi chưa có lần đọc incident thành công.

Điều kiện này chỉ kiểm tra sự hiện diện của một URL đã quan sát. Nó không chứng minh mọi nhận định trong answer đều được nguồn hỗ trợ.

### Bước 8. Chạy eval sau cải tiến

Giữ nguyên provider, model, judge, snapshot, dataset, max steps và các tham số khác. Bỏ `--baseline`:

```powershell
python evals/run_evals.py --env-file .env --output eval_after.json
```

Hai file phải khác `agent_version` nhưng có `config` giống nhau. Không đổi model giữa chừng để làm đẹp điểm.

### Bước 9. Tiếp tục khi bị gián đoạn và xử lý lỗi API

Sau khi sửa lỗi, dùng đúng lệnh tương ứng:

```powershell
python evals/run_evals.py --env-file .env --baseline --resume --output eval_before.json
python evals/run_evals.py --env-file .env --resume --output eval_after.json
```

Chỉ chạy lệnh của bộ cần tiếp tục. Runner giữ case đã chấm; nếu agent đã hoàn thành mà judge lỗi, runner giữ answer/trace và gọi lại judge. Runner từ chối resume nếu file khác cấu hình hoặc phiên bản agent. Không sửa tay điểm và trace.

| HTTP | Hướng xử lý |
|---|---|
| 401 | Kiểm tra `GROQ_API_KEY` được tạo tại Groq Console, lưu file rồi chạy với `--env-file .env`. |
| 403 | Kiểm tra quyền model/project và thông tin provider; request của adapter đã có User-Agent nhận diện ứng dụng. |
| 404 | Kiểm tra model còn được Groq phục vụ và đúng model ID. |
| 400 / 422 | Kiểm tra tham số, định dạng request hoặc lỗi tool call do model tạo. |
| 413 | Request vượt giới hạn kích thước; đọc lỗi trước khi tiếp tục. |
| 429 | Kiểm tra RPM/RPD/TPM/TPD trên Groq Console, chờ đúng thời gian rồi resume. |
| 500 / 503 | Lỗi dịch vụ; chờ rồi resume. |

Đối chiếu [mã lỗi Groq](https://console.groq.com/docs/errors) và [rate limits](https://console.groq.com/docs/rate-limits). Terminal in cả nguyên nhân provider khi eval dừng. Để thay khoảng cách request, đặt `--request-interval` ngay từ đầu và giữ cùng giá trị khi resume cũng như khi so sánh hai bộ.

### Bước 10. So sánh kết quả và chuẩn bị nộp

```powershell
$before = Get-Content eval_before.json -Raw -Encoding UTF8 | ConvertFrom-Json
$after = Get-Content eval_after.json -Raw -Encoding UTF8 | ConvertFrom-Json
$before.summary
$after.summary
$before.config
$after.config
```

Chỉ kết luận đã hoàn thành eval khi mỗi file đủ 22 case được chấm, `progress.complete` bằng `true` và `summary.score_0_100` khác `null`. `partial_mean_0_100` chỉ là trung bình phần đã chấm.

`NOTES.md` cần đủ năm mục: case cụ thể; bằng chứng trace; thay đổi; so sánh điểm/token/chi phí; giới hạn. Nếu điểm không tăng thì ghi đúng kết quả. Nếu không có event sửa nguồn, không được nói model đã trải qua lượt sửa đó.

Khi demo, giải thích được một chuỗi `get_status` → `get_incident_details` → answer có nguồn và một trường hợp lỗi. Giữ nguyên `fixtures/`, `evals/cases.json`, `evals/scenarios.py`, `evals/grading.py`, tests và tài liệu gốc. Các file debug thêm trong quá trình sửa đã được dọn; không xóa file của đề chỉ vì chưa dùng.

Repo GitHub phải theo lớp L3A/L3B và mẫu trong `SUBMISSION.md`. Sau khi đủ kết quả và cập nhật ghi chú:

```powershell
git status --short
git ls-files | Select-String '\.env'
git add agent.py providers.py run.py evals/run_evals.py README.md NOTES.md .env.example eval_before.json eval_after.json
git commit -m "Hoan thien Status Investigation Agent va phan tich eval"
git push
```

Chỉ `.env.example` được đưa vào Git; `.env` thật phải được ignore. Mở repo khi chưa đăng nhập để xác nhận public, rồi nộp URL lên [LMS](https://aithucchien.vinuni.edu.vn). Không nộp một bộ còn pending như thể đã hoàn thành.
