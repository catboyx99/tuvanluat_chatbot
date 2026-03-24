# Deployment Plan: Law Consultant ChatBot

## Context
Dự án đã hoàn thiện và chạy OK trên local Docker. Tài liệu này hướng dẫn deploy lên server doanh nghiệp (hỗ trợ cả Linux VPS và Windows Server) với domain riêng, truy cập public qua HTTPS.

## Kiến trúc Deploy

```
Internet → Domain (HTTPS:443)
              ↓
         Reverse Proxy (Nginx)
              ↓
    ┌─────────┴──────────┐
    ↓                    ↓
 Frontend:3000      Backend:8000
 (Next.js)          (FastAPI)
    └────────→───────────┘
       Docker internal network
```

---

## Hướng 1: Linux VPS (Ubuntu/Debian) — Khuyến nghị

### Bước 1 — Cài đặt môi trường
```bash
apt update && apt install docker.io docker-compose-plugin -y
```

### Bước 2 — Clone project
```bash
git clone https://github.com/catboyx99/tuvanluat_chatbot.git
cd tuvanluat_chatbot
```

### Bước 3 — Tạo file `.env`
```
GEMINI_API_KEY=<api-key>
```

### Bước 4 — Build & chạy Docker
```bash
docker compose up -d --build
```
Lần đầu sẽ tự build images + ingest data vào ChromaDB (~2-3 phút).

### Bước 5 — Cài Nginx reverse proxy + SSL
```bash
apt install nginx certbot python3-certbot-nginx -y
```

Tạo file `/etc/nginx/sites-available/tuvanluat`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;           # quan trọng cho streaming
        proxy_read_timeout 300s;
    }
}
```

Enable site + cấp SSL:
```bash
ln -s /etc/nginx/sites-available/tuvanluat /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d yourdomain.com
```
Certbot tự thêm HTTPS config và tự gia hạn SSL.

### Bước 6 — Mở firewall
```bash
ufw allow 80
ufw allow 443
```

### Bước 7 — Trỏ domain
Vào DNS provider, tạo A record: `yourdomain.com → IP VPS`

---

## Hướng 2: Windows Server

### Bước 1 — Cài Docker Desktop for Windows
- Tải Docker Desktop từ docker.com
- Enable WSL 2 backend (khuyến nghị) hoặc Hyper-V

### Bước 2 — Clone project
```powershell
git clone https://github.com/catboyx99/tuvanluat_chatbot.git
cd tuvanluat_chatbot
```

### Bước 3 — Tạo file `.env` (giống Linux)

### Bước 4 — Build & chạy Docker
```powershell
docker-compose up -d --build
```

### Bước 5 — Reverse Proxy + SSL

**Option A — IIS + URL Rewrite (dùng hạ tầng Windows sẵn có)**
1. Cài IIS qua Server Manager → Add Roles → Web Server
2. Cài URL Rewrite module + ARR (Application Request Routing)
3. Tạo site trỏ đến domain
4. Cấu hình Reverse Proxy rules:
   - `/` → `http://localhost:3000`
   - `/api/*` → `http://localhost:8000`
5. Cài win-acme cho SSL: https://www.win-acme.com/

**Option B — Nginx for Windows (đơn giản hơn)**
- Tải Nginx for Windows
- Dùng cùng config như Hướng 1 Bước 5
- SSL: dùng win-acme hoặc mua SSL cert

### Bước 6 — Mở Windows Firewall
- Mở port 80 và 443 trong Windows Firewall → Inbound Rules → New Rule → Port

### Bước 7 — Trỏ domain (giống Linux)

---

## Production Docker Compose

Khi deploy production, dùng thêm file override `docker-compose.prod.yml`:
```yaml
services:
  frontend:
    restart: always

  backend:
    restart: always
```

Chạy production:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`restart: always` đảm bảo container tự khởi động lại khi server reboot hoặc crash.

---

## Verification Checklist
- [ ] `docker compose ps` — cả 2 container Running
- [ ] `curl http://localhost:3000` — frontend OK
- [ ] `curl http://localhost:8000/health` — backend OK (trả `{"status":"ok"}`)
- [ ] Truy cập `https://yourdomain.com` — hiện giao diện chat
- [ ] Hỏi thử câu pháp luật — nhận streaming response với citation
- [ ] `curl -I https://yourdomain.com` — kiểm tra SSL certificate OK
