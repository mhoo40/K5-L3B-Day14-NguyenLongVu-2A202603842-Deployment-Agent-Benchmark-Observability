# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. API key hardcode trong code
2. Không có health check endpoint
3. Debug mode bật cứng
4. Không xử lý SIGTERM gracefully
5. Config không đến từ environment
6. In secret ra console/log
7. không có fallback

### Exercise 1.2: Kết quả gọi bản develop
```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}

backend:
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.
INFO:     127.0.0.1:57027 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```
Chạy được nhưng chưa sẵn sàng

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config  | Config trên app.py | Config được lưu vào config.py | Tránh lộ secret khi push lên GitHub; cho phép đổi cấu hình giữa dev/staging/prod mà không cần sửa code hay rebuild image |
| Network Binding | host="localhost", port=8000 | host="0.0.0.0", port=int(os.getenv("PORT", "8000")) | localhost chỉ nhận kết nối nội bộ; 0.0.0.0 cho phép Docker/cloud router gửi traffic vào container, còn biến PORT tương thích với cổng động của cloud platform |
| Health & Readiness  | Không có | Có GET /health và GET /ready | Cloud orchestrator và load balancer dựa vào /health để tự restart container bị treo và /ready để chỉ điều hướng traffic khi app đã khởi tạo xong |
| Logging  | Dùng print() dạng text tự do, in cả API key | Dùng thư viện logging xuất chuẩn JSON, chỉ log metadata, không log secret | Log JSON giúp các hệ thống như Datadog, Loki, CloudWatch dễ index, lọc và tạo cảnh báo tự động mà không làm rò rỉ dữ liệu nhạy cảm |
| Shutdown  | Tắt đột ngột khi tiến trình bị kill | Dùng lifespan context manager và signal.signal | Khi deploy phiên bản mới hoặc scale down, container có thời gian hoàn tất các request đang xử lý dở và đóng kết nối sạch sẽ trước khi thoát |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image**: python 3.11
2. **Working directory**: /app
3. **COPY requirements.txt trước** do cơ chế Docker layer cache: File requirements.txt ít khi thay đổi hơn so với source code, Khi chỉ sửa code mà không đổi thư viện, Docker sẽ dùng lại cache của bước COPY requirements.txt và RUN pip install, giúp build lại image chỉ mất vài giây thay vì phải tải và cài lại toàn bộ thư viện từ đầu
4. **CMD vs ENTRYPOINT khác nhau thế nào**?

`*CMD*`: Định nghĩa lệnh mặc định chạy khi container khởi động. Lệnh này dễ dàng bị ghi đè nếu người dùng truyền thêm tham số vào cuối lệnh docker run.

`*ENTRYPOINT*`: Định nghĩa chương trình cố định luôn luôn chạy khi container khởi động. Các tham số truyền thêm lúc docker run sẽ được nối tiếp làm argument cho ENTRYPOINT chứ không ghi đè nó (muốn đổi phải dùng cờ --entrypoint). Thông thường, người ta kết hợp ENTRYPOINT để cố định lệnh thực thi và CMD để truyền các tham số mặc định có thể thay đổi.

### Exercise 2.2: Multi-stage build
- **Stage 1**: Image của stage này chỉ dùng trung gian để biên dịch và không được đem đi deploy.
- **Stage 2**: Chỉ copy các thư viện đã biên dịch xong từ Stage 1 cùng với source code.
- **Tại sao image nhỏ hơn**: Dùng python:3.11-slim thay vì bản đầy đủ python:3.11 chứa nhiều công cụ hệ thống dư thừa. Các công cụ biên dịch nặng như gcc, libpq-dev, file header và cache của apt/pip chỉ nằm lại ở Stage 1 và bị bỏ đi hoàn toàn khi sang Stage 2; image cuối cùng chỉ chứa đúng Python runtime, các package đã build và mã nguồn cần thiết.

### Exercise 2.3: Image size comparison
- Develop: 426 MB
- Production: 57.4 MB
- Difference: 88%

### Exercise 2.4: Docker Compose stack
```
                    External Client (Browser / curl)
                                  │
                         HTTP :80 / HTTPS :443
                                  ▼
                  ┌───────────────────────────────┐
                  │             nginx             │
                  │  (Reverse Proxy & Load Bal.)  │
                  └───────────────┬───────────────┘
                                  │  http://agent:8000 (internal network)
                                  ▼
                  ┌───────────────────────────────┐
                  │             agent             │
                  │      (FastAPI AI Agent)       │
                  └───────┬───────────────┬───────┘
                          │               │
        redis://redis:6379/0             http://qdrant:6333
                          ▼               ▼
              ┌───────────────────┐   ┌───────────────────┐
              │       redis       │   │      qdrant       │
              │ (Cache/RateLimit) │   │    (Vector DB)    │
              └─────────┬─────────┘   └─────────┬─────────┘
                        │                       │
                        ▼                       ▼
                [( redis_data )]        [( qdrant_data )]
```


## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://brokeass-production.up.railway.app

### Exercise 3.2: So sánh `render.yaml` và `railway.toml`
| Tiêu chí | `render.yaml` (Render Blueprint) | `railway.toml` (Railway Config as Code) | Vì sao có sự khác biệt này? |
| :--- | :--- | :--- | :--- |
| **Định dạng file** | **YAML** (`.yaml`) — hỗ trợ cấu trúc phân cấp sâu, danh sách và nhiều resource trong một file. | **TOML** (`.toml`) — cú pháp `[section]` phẳng, ngắn gọn, dễ đọc cho cấu hình của một service đơn lẻ. | Render thiết kế file Blueprint như một bản khai báo hạ tầng tổng thể (tương tự Docker Compose), trong khi Railway tập trung vào cấu hình tối giản cho từng service riêng biệt. |
| **Phạm vi khai báo (Scope)** | **Multi-service (Toàn bộ hệ thống):** Có thể định nghĩa cùng lúc Web Service, Redis (`type: redis`), PostgreSQL, Cron Job, Disk và nối biến môi trường tự động giữa chúng (`fromService`). | **Single-service (1 service duy nhất):** Chỉ cấu hình cách build, deploy và healthcheck cho đúng service chứa file đó; Redis hoặc database phải tạo riêng trên dashboard hoặc CLI. | Render quản lý hạ tầng theo mô hình Blueprint đồng bộ từ Git, còn Railway quản lý các service trong một Project theo dạng từng khối độc lập rồi liên kết qua biến môi trường (`${{Redis.REDIS_URL}}`). |
| **Cách build & chạy (Build & Start)** | Khai báo trực tiếp `runtime` (`python` hoặc `docker`), `buildCommand` (`pip install...`) và `startCommand` (`uvicorn...`) ngay trong file. | Khai báo `[build]` (`builder = "DOCKERFILE"` hoặc Railpack/Nixpacks) và `[deploy]` (`startCommand = "..."`), ưu tiên tự nhận diện từ `Dockerfile` hoặc mã nguồn. | Railway hướng tới trải nghiệm "zero-config" (tự động build từ `Dockerfile` nếu có), còn Render cho phép kiểm soát tường minh từng lệnh build/start cho từng môi trường runtime. |
| **Khai báo biến môi trường (Env Vars)** | Khai báo trực tiếp danh sách `envVars:` trong file (hỗ trợ `value`, `sync: false` để nhập tay trên dashboard, hoặc `generateValue: true` để tự sinh secret). | **Không** khai báo biến môi trường trực tiếp trong `railway.toml`; toàn bộ biến môi trường và secret được quản lý qua Dashboard hoặc lệnh `railway variables set`. | Tách biệt hoàn toàn cấu hình hạ tầng (commit lên Git) với cấu hình runtime/secrets (lưu trên nền tảng Railway) để giảm rủi ro lộ thông tin nhạy cảm. |
| **Health Check & Restart Policy** | Dùng `healthCheckPath: /health` và `autoDeploy: true` (nền tảng tự quản lý restart khi container lỗi). | Cấu hình chi tiết trong `[deploy]` gồm `healthcheckPath = "/health"`, `healthcheckTimeout = 30`, `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 3`. | Railway cho phép tinh chỉnh trực tiếp chính sách khởi động lại và ngưỡng timeout của healthcheck ngay trong file cấu hình của service. |
| **Cơ chế kích hoạt Deploy** | Deploy qua **Git Blueprint** (Render đọc `render.yaml` ở thư mục gốc repo mỗi khi push code lên GitHub). | Deploy qua cả **CLI (`railway up`)** lẫn **GitHub integration** (Railway đọc `railway.toml` ở thư mục gốc hoặc thư mục service được chỉ định). | Railway hỗ trợ đẩy code trực tiếp từ máy local qua CLI mà chưa cần push lên Git, phù hợp để test nhanh trong lúc phát triển. |

## Part 4: API Security

### Exercise 4.1-4.3: Test results

- **API key được check ở đâu**? Check trong verify_api_key(api_key: str = Security(api_key_header))
- **Điều gì xảy ra nếu sai key**? Bị Exception detail="Invalid API key."
- **Làm sao rotate key**? thêm -H "X-API-Key: demo-key-change-in-production"


**API Key authentication**:
```
curl.exe -i -X POST "http://localhost:8000/ask" -H "X-API-Key: demo-key-change-in-production" -H "Content-Type: application/json" -d '{\"question\": \"Hello\"}'
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:56:35 GMT
server: uvicorn
content-length: 145
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

**JWT authentication**:
```
curl.exe -i -X POST "http://localhost:8000/ask" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdHVkZW50Iiwicm9sZSI6InVzZXIiLCJpYXQiOjE3OTU2ODQwOTAsImV4cCI6MTc5NTY4NzY5MH0.yRVifz0VUgjesNt4r60q1477OwS_YRfh02O7nb6DH2Y" -H "Content-Type: application/json" -d '{\"question\": \"Explain JWT\"}'

HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 09:10:58 GMT
server: uvicorn
content-length: 192
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Explain JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

**Rate limiting**:

- **Algorithm nào được dùng**? Sliding window
- **Limit là bao nhiêu requests/minute**? User: 10 req/phút & Admin: 100 req/phút
- **Làm sao bypass limit cho admin**? Khởi tạo hai instance RateLimiter riêng biệt cho từng tier -> Điều hướng theo role trong JWT payload

```
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```


### Exercise 4.4: Cost guard implementation

**Lưu trữ tập trung trên Redis**: Chi phí tích lũy của từng user được lưu theo khóa budget:{user_id}:{YYYY-MM} (ví dụ budget:student:2026-11) để đồng bộ giữa mọi worker/instance và tự động reset sang tháng mới.

**Kiểm tra trước khi gọi LLM**: Trước khi xử lý request, hệ thống đọc số tiền đã dùng hiện tại trong tháng (r.get(key)) và cộng thử với chi phí ước tính (estimated_cost). Nếu vượt quá ngưỡng cho phép ($10), request lập tức bị chặn với mã lỗi HTTP 402 Payment Required.

**Cộng dồn & đặt thời hạn (TTL)**: Nếu còn ngân sách, hệ thống cộng dồn chi phí vào Redis (r.incrbyfloat(key, estimated_cost)) và đặt thời gian tự hủy key khoảng 32 ngày (r.expire(key, 32 * 24 * 3600)) để dọn dẹp dữ liệu các tháng cũ. 

## Part 5: Scaling & Reliability
### 1. Phân biệt `/health` (Liveness Probe) và `/ready` (Readiness Probe)

| Tiêu chí | `/health` (Liveness Probe) | `/ready` (Readiness Probe) |
| :--- | :--- | :--- |
| **Mục đích** | Kiểm tra xem tiến trình (process) của container còn sống và không bị treo hay không. | Kiểm tra xem service đã sẵn sàng phục vụ traffic thực tế hay chưa (đã kết nối được tới Redis, database, v.v.). |
| **Cách kiểm tra** | Trả về `200 OK` ngay lập tức mà không gọi sang các dịch vụ phụ thuộc bên ngoài. | Thực hiện kiểm tra kết nối tới các dependency (ví dụ `redis.ping()`); trả về `200 OK` nếu thành công hoặc `503 Service Unavailable` nếu lỗi. |
| **Hành động của Orchestrator khi lỗi** | **Khởi động lại (restart) container** vì tiến trình đã chết hoặc rơi vào trạng thái deadlock. | **Ngắt định tuyến traffic (bỏ khỏi load balancer)** tạm thời nhưng **không kill container**, chờ dependency hồi phục rồi mới gửi request trở lại. |

---

### 2. Tại sao lưu state trong RAM gây lỗi khi scale ngang và cách Redis giải quyết

* **Vấn đề khi lưu state trong RAM (Stateful):** Khi scale ứng dụng lên nhiều replicas (`--scale agent=3`), mỗi container có vùng nhớ RAM hoàn toàn tách biệt. Nếu lưu lịch sử hội thoại (`conversation_history`) trong một biến `dict` của Python trên RAM:
  1. Request 1 của user đi vào `instance-A` và được lưu vào RAM của `instance-A`.
  2. Request 2 của cùng user đó bị Load Balancer (Nginx) điều hướng sang `instance-B` — nơi không có dữ liệu của user này, dẫn đến mất ngữ cảnh hội thoại.
  3. Khi container bị restart hoặc deploy phiên bản mới, toàn bộ dữ liệu trong RAM bị xóa sạch.
* **Cách Redis giải quyết (Stateless Design):** Tách toàn bộ state ra khỏi các container ứng dụng và lưu tập trung trên **Redis** (theo key `session:{session_id}`). Nhờ đó, mọi replica của `agent` đều trở nên **stateless** (không giữ trạng thái riêng): bất kỳ instance nào nhận request cũng đọc và ghi lịch sử hội thoại từ cùng một nguồn dữ liệu chung trên Redis.

---

### 3. Kết quả chạy `python test_stateless.py` & Giải thích

#### Output thực tế:

```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 361261a1-3648-40a0-8fbe-48508dead1cf

Request 1: [instance-b0f076]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-015243]
  Q: Why do we need containers?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 3: [instance-9920cd]
  Q: What is Kubernetes?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 4: [instance-b0f076]
  Q: How does load balancing work?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 5: [instance-015243]
  Q: What is Redis used for?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-9920cd', 'instance-b0f076', 'instance-015243'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: What is Kubernetes?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
  [user]: How does load balancing work?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: What is Redis used for?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...

✅ Session history preserved across all instances via Redis!
```

================================================================
  Production Readiness Check — Day 14 Lab
================================================================

✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Dockerfile tồn tại
     ✅ requirements.txt tồn tại
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn (slim / alpine / distroless) — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 1s
     ✅ Docker: image < 500 MB — 238 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
     ✅ docker-compose.yml tồn tại
     ✅ Có service agent (build từ Dockerfile) + redis — services: agent, redis — đọc bằng docker compose config
     ✅ Service agent kết nối redis (REDIS_URL + depends_on)

✅ 3. .dockerignore
     ✅ .dockerignore tồn tại và có nội dung
     ✅ .dockerignore loại trừ .env (secrets)
     ✅ .dockerignore loại trừ __pycache__, venv

✅ 4. Health check endpoint (GET /health)
     ✅ Code có route /health
     ✅ Khi chạy: GET /health → 200 — uvicorn --workers 2

✅ 5. Readiness endpoint (GET /ready)
     ✅ Code có route /ready
     ✅ Khi chạy: GET /ready → 200
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
     ✅ Code đọc header X-API-Key
     ✅ Khi chạy: thiếu / sai API key → 401
     ✅ Khi chạy: API key đúng → 200

✅ 7. Rate limiting
     ✅ Code trả HTTP 429 khi vượt giới hạn
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Code trả HTTP 402 khi hết budget
     ✅ Khi chạy: hết budget → 402 — 402 ở request thứ 1

✅ 9. Config từ environment variables
     ✅ app/config.py đọc biến môi trường
     ✅ .env.example liệt kê đủ biến cấu hình
     ✅ .env nằm trong .gitignore
     ✅ Không hard-code secret trong code
     ✅ Khi chạy: agent dùng AGENT_API_KEY và RATE_LIMIT_PER_MINUTE từ env

✅ 10. Structured logging
     ✅ Code ghi log dạng JSON
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 12 dòng JSON

⚠️  11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ⚠️  Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — chưa kiểm tra được — Windows không gửi được SIGTERM (phần Docker sẽ kiểm tra)
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 0.7s

✅ 12. Public URL ready (Railway / Render config)
     ✅ Có railway.toml hoặc render.yaml (không chỉ toàn comment)
     ✅ render.yaml: web service + healthCheckPath /health
     ✅ render.yaml: secret không ghi thẳng giá trị (generateValue / sync: false)
     ✅ App lắng nghe theo biến PORT do platform cấp

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ⚠️  Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 11/12 tiêu chí đạt · 41/41 checks passed
  ⚠️  Chưa kiểm tra được: Graceful shutdown
  ❌ CHƯA ĐẠT — còn tiêu chí chưa kiểm tra được (⚠️). Chạy đầy đủ trên máy có Docker.