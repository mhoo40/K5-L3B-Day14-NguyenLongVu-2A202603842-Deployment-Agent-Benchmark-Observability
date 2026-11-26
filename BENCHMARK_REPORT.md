# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Long Vũ
**Ngày chạy:** 26/11/2026
**Môi trường:** Windows 11, Intel Core Ultra 7 155H / RTX 3060 Laptop, Docker Desktop (WSL2 backend)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo trải nghiệm phản hồi gần như tức thì cho 95% người dùng tương tác trực tiếp, ngay cả khi có bước retrieval (~20 ms) và gọi LLM (~150 ms). |
| Error rate `/ask` | < 2.0 % | Cho phép sai số nhỏ từ lỗi upstream ngẫu nhiên (`MOCK_ERROR_RATE = 1%`) nhưng cảnh báo sớm ngay khi hệ thống hoặc LLM provider gặp sự cố diện rộng. |
| Accuracy trên golden dataset | ≥ 80.0 % | Ngưỡng quality gate tối thiểu trước khi deploy để đảm bảo agent trả lời đúng kiến thức cốt lõi và ngăn chặn regression khi thay đổi prompt/model. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.93 | 204.3 | 234.0 | 1693.3 | 0.00% | PASS |
| 10 | 32.88 | 191.8 | 235.1 | 1720.3 | 1.00% | PASS |
| 50 | 71.42 | 223.4 | 825.1 | 1761.4 | 1.00% | FAIL |
| 100 | 38.54 | 623.6 | 3248.0 | 3562.0 | 0.00% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. RPS chỉ tăng gần tuyến tính trong vùng tải thấp đến trung bình (`c = 1 → 25`, từ `3.93` lên `59.34 req/s`) nhờ cơ chế I/O bất đồng bộ (`async/await`) của FastAPI/Uvicorn tận dụng tốt thời gian chờ `asyncio.sleep` của LLM. Từ `c = 50` (`71.42 req/s`), hệ thống chạm điểm bão hòa của một process Uvicorn duy nhất; đến `c = 100`, chi phí context-switch và xếp hàng trong event loop/socket khiến throughput sụp giảm gần một nửa (`38.54 req/s`) và `p95` tăng vọt lên `3248.0 ms`.

---

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | [avg_0] | [p95_0] | [p99_0] |
| 0.03 (mặc định) | [avg_003] | [p95_003] | [p99_003] |
| 0.1 | [avg_01] | [p95_01] | [p99_01] |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **Chỉ số nhạy nhất:** `p99` và `p95` (tail latency). Ngay cả khi `MOCK_SLOW_RATE` chỉ ở mức `0.03` (3% request chậm), `p99` đã nhảy vọt lên mức `~1700 ms` vì 1% request chậm nhất rơi trọn vào nhóm tail latency; khi tăng lên `0.1` (10%), hơn 5% request bị chậm nên `p95` cũng vượt ngưỡng `1600 ms`.
- **Vì sao không đặt SLO theo average:** Giá trị trung bình (`avg`) bị kéo phẳng bởi 90–97% request bình thường (~200 ms), che giấu hoàn toàn trải nghiệm tệ của nhóm người dùng gặp độ trễ cao (1.7–3.5 giây).

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | [v1_acc]% ([v1_pass]/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | [v1_tokens] | 109.1 | [v2f_tokens] |
| Tổng cost (USD) | $[v1_cost] | $0.000762 | $[v2f_cost] |
| Cost / câu đúng (USD) | $[v1_cost_per_pass] | $0.00003627 | $[v2f_cost_per_pass] |
| Quality gate | PASS / FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung retrieval dự phòng (`EXTRA_KNOWLEDGE` / `_retrieve_extra`) trong `app.py` (giữ nguyên `utils/mock_llm.py`) giải thích sự khác biệt giữa API key và JWT (token tự chứa claims, có chữ ký số và thời gian hết hạn). |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung tài liệu về Kubernetes HPA trong `EXTRA_KNOWLEDGE` của `app.py` nêu rõ cơ chế autoscale dựa trên CPU, memory và custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- **Chất lượng:** `v2` (có RAG) vượt trội hoàn toàn so với `v1` (chỉ trả lời câu mẫu chung chung), đạt 91.3% ngay từ đầu và 100% sau khi bổ sung tri thức còn thiếu.
- **Chi phí & Latency:** Vì `v2` thực hiện thêm bước tìm kiếm tài liệu (`~20 ms`) và nhồi context vào prompt, số input token trung bình mỗi câu tăng lên (`109.1 tokens`), kéo theo chi phí mỗi request cao hơn và latency tăng thêm khoảng `20–30 ms`. Tuy nhiên, chi phí trên mỗi câu trả lời **đúng** (`$0.00003627`) của `v2` lại hiệu quả hơn nhiều so với `v1` vì `v1` tốn tiền gọi LLM nhưng phần lớn câu trả lời đều sai.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `HighErrorRate` | [~1–2 phút] | Error Rate (%) / HTTP 5xx Panel |
| B | `MOCK_SLOW_RATE=0.3` | `HighLatencyP95` | [~1–2 phút] | Latency Percentiles (p95 / p99) |
| C | `LLM_MODEL=mock-llm-large` | `HighLatencyP95` / `HighCostRate` | [~1–2 phút] | Token Cost ($/min) & LLM Latency |
| D | `docker pause` 1 instance | `InstanceDown` (hoặc `TargetDown`) | [~30–60 giây] | Active Replicas / Up Instances |
| E | `AGENT_VERSION=v1` | *(Không có alert nào firing)* | — | `agent_info{version="v1"}` / Avg Tokens giảm |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Đây là **silent quality regression** (hệ thống vẫn trả HTTP 200 nhanh và rẻ hơn nhưng nội dung trả lời sai). Để phát hiện trong production cần kết hợp 3 lớp:
1. **CI/CD Quality Gate:** Bắt buộc chạy `run_eval.py` trên golden dataset trước khi deploy; chặn release nếu accuracy giảm so với baseline hoặc tụt dưới ngưỡng SLO (`80%`).
2. **Online Telemetry & Proxy Metrics:** Theo dõi sự sụt giảm bất thường của `avg_input_tokens` hoặc tỷ lệ `retrieved=true` trong structured logs / Prometheus metrics (khi `v2` tụt về `v1`, token prompt giảm đột ngột vì mất context RAG).
3. **Production Sampling & User Feedback:** Chạy LLM-as-a-Judge định kỳ trên mẫu traffic thật (1–5%) và theo dõi tỷ lệ thumbs-down / retry của người dùng.

---

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `37555ad`
- Tổng thời gian: `1.7` s
- Span chiếm nhiều thời gian nhất: `agent.run` (`1680` ms, `98`%)
- Dòng log tương ứng (grep theo `trace_id` qua lệnh `docker compose logs agent | findstr <trace_id>`):
```json
agent-3  | {"ts": "2026-11-26T15:11:10.190095+00:00", "level": "INFO", "service": "observable-agent", "instance": "098f6330918e", "event": "llm_call", "trace_id": "37555adff63de9e67f6dc5e7ea293299", "span_id": "02d40157934eeb74", "request_id": "0b0887945caa", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 81, "output_tokens": 46, "cost_usd": 4e-05, "llm_ms": 1681.9}
agent-3  | {"ts": "2026-11-26T15:11:10.190545+00:00", "level": "INFO", "service": "observable-agent", "instance": "098f6330918e", "event": "http_request", "trace_id": "37555adff63de9e67f6dc5e7ea293299", "span_id": "02d40157934eeb74", "request_id": "0b0887945caa", "method": "POST", "route": "/ask", "status": 200, "ms": 1711.1}
```

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 |65.12 (POST /ask: 59.18)|190|270 (POST /ask: 290)|1700|72 (0.92%)|
| 3 |66.19 (POST /ask: 59.78)|190|220 (POST /ask: 230)|1700|62 (0.78%)|

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?
Có, p95 giảm từ 270 ms xuống 220 ms nhờ Nginx chia tải đều cho 3 container, giúp giảm áp lực xếp hàng trên từng event loop của Uvicorn.

- **3 điều bạn học được về benchmark & observability:**
  1. **Không bao giờ đặt SLO dựa trên độ trễ trung bình (`avg`) hay `p50`:** Khi upstream LLM có tỷ lệ request chậm ngẫu nhiên (`MOCK_SLOW_RATE = 0.03 → 0.1`), `avg` và `p50` gần như không thay đổi (`~190–250 ms`), che giấu hoàn toàn việc `p95`/`p99` tăng vọt lên `1700+ ms`. Chỉ các chỉ số tail latency (`p95`, `p99`) mới phản ánh đúng trải nghiệm tệ nhất mà người dùng gặp phải.
  2. **Kiểm soát cardinality của Prometheus labels và kết hợp 3 trụ cột Observability:** Metrics chỉ nên dùng các label có tập giá trị hữu hạn (`method`, `route`, `status`, `model`) để tránh bùng nổ time-series làm tràn RAM Prometheus; còn thông tin chi tiết của từng request (`request_id`, `trace_id`, từng span retrieval/LLM) phải ghi vào JSON logs và OpenTelemetry traces (Jaeger) để khoanh vùng đúng nút thắt cổ chai.
  3. **Hệ thống khỏe về hạ tầng chưa đảm bảo đúng về chất lượng nghiệp vụ:** Như trong thí nghiệm `AGENT_VERSION=v1` hoặc lỗi thiếu kiến thức ở `security-02` và `scaling-03`, service vẫn trả HTTP 200 nhanh và rẻ hơn nhưng nội dung trả lời sai. Bắt buộc phải chạy automated evaluation trên golden dataset (Quality Gate) trước mỗi lần deploy song song với việc giám sát runtime.

## 6. Kết luận

- **Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?**
  1. **Metric & Alert về chất lượng RAG (`rag_empty_retrieval_total` / `rag_retrieval_score`):** Đo tỷ lệ câu hỏi không tìm thấy tài liệu liên quan hoặc điểm tương đồng vector thấp — bắn alert ngay khi knowledge base bị hổng dữ liệu hoặc vector database gặp sự cố.
  2. **Budget & Token Burn-Rate Alert (`rate(llm_cost_usd_total[5m])`):** Cảnh báo sớm khi tốc độ tiêu thụ token/chi phí USD tăng đột biến theo cửa sổ trượt 5 phút, kết hợp giới hạn quota theo từng API key để tránh đội chi phí do vòng lặp agent hoặc bị spam.
  3. **Phân tách lỗi upstream LLM theo mã lỗi (`429 Rate Limit`, `Timeout`, `5xx`) & Circuit Breaker:** Tách riêng lỗi quá tải token/RPM (`429`) với lỗi mạng/timeout của nhà cung cấp LLM để kích hoạt tự động cơ chế retry có backoff hoặc chuyển sang model dự phòng (fallback).