# Deployment Information

## Public URL
https://ai-agent-du7f.onrender.com

## Platform
Render (Blueprint / Docker runtime, Singapore region)

## Test Commands

### Health Check
```bash
curl [https://ai-agent-du7f.onrender.com/health](https://ai-agent-du7f.onrender.com/health)
# Expected: {"status": "ok"}
```

### Readiness Check
```bash
curl [https://ai-agent-du7f.onrender.com/ready](https://ai-agent-du7f.onrender.com/ready)
# Expected: {"ready": true}
```

### API Test (with authentication)
```bash
curl -X POST [https://ai-agent-du7f.onrender.com/ask](https://ai-agent-du7f.onrender.com/ask) \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

## Environment Variables Set
- `ENVIRONMENT` (`production`)
- `PORT` (injected automatically by Render, `10000`)
- `REDIS_URL` (linked internal connection string from Render Redis `agent-cache`)
- `AGENT_API_KEY` (auto-generated secret via Render Blueprint)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`1.0`)

## Screenshots
- [Deployment dashboard](screenshots/Render1.png)
- [Service running](screenshots/Render2.png)
- [Test results](screenshots/Render3-5.png)