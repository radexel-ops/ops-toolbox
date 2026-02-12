# 05. Deployment Guide - VibeOps

> **문서 목적**: DigitalOcean 배포 가이드 및 서버 설정 방법을 정의합니다.

---

## 1. 인프라 개요

### 1.1 선택: DigitalOcean Droplet

| 항목 | 권장 사양 | 이유 |
|------|----------|------|
| OS | Ubuntu 24.04 LTS | 안정성, 장기 지원 |
| RAM | 8GB | 다중 에이전트, Claude Code 동시 구동 |
| CPU | 2 vCPU | 기본 작업 처리 |
| Storage | 50GB SSD | DB, 로그, 다운로드 파일 |
| Region | Singapore (sgp1) | 한국에서 가장 가까움 |

### 1.2 예상 비용

| 구성 | 월 비용 |
|------|---------|
| Basic Droplet (8GB) | $48/월 |
| (선택) 백업 | +$9.60/월 |
| **합계** | **약 $48~58/월** |

---

## 2. 초기 설정

### 2.1 Droplet 생성

```bash
# 1. DigitalOcean 콘솔에서 Droplet 생성
# - Choose an image: Ubuntu 24.04 (LTS) x64
# - Choose a plan: Basic, $48/mo (8GB / 2 CPU)
# - Choose datacenter: Singapore (sgp1)
# - Authentication: SSH Key (권장)

# 2. SSH 접속
ssh root@YOUR_DROPLET_IP
```

### 2.2 기본 보안 설정

```bash
# 시스템 업데이트
apt update && apt upgrade -y

# 새 사용자 생성 (root 직접 사용 지양)
adduser vibeops
usermod -aG sudo vibeops

# SSH 키 복사
mkdir -p /home/vibeops/.ssh
cp ~/.ssh/authorized_keys /home/vibeops/.ssh/
chown -R vibeops:vibeops /home/vibeops/.ssh

# 방화벽 설정
ufw allow OpenSSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw enable

# SSH 설정 강화 (선택)
# /etc/ssh/sshd_config 편집
# - PermitRootLogin no
# - PasswordAuthentication no
```

### 2.3 필수 패키지 설치

```bash
# vibeops 사용자로 전환
su - vibeops

# Python 3.11+ 설치
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# 기타 필수 패키지
sudo apt install -y \
    git \
    tmux \
    nginx \
    sqlite3 \
    curl \
    wget \
    htop

# Chrome 설치 (Selenium용)
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install -y google-chrome-stable

# ChromeDriver 설치
CHROME_VERSION=$(google-chrome --version | grep -oP '\d+' | head -1)
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION -O /tmp/chromedriver_version
DRIVER_VERSION=$(cat /tmp/chromedriver_version)
wget https://chromedriver.storage.googleapis.com/$DRIVER_VERSION/chromedriver_linux64.zip -O /tmp/chromedriver.zip
unzip /tmp/chromedriver.zip -d /tmp/
sudo mv /tmp/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
```

---

## 3. 프로젝트 배포

### 3.1 프로젝트 클론

```bash
# 프로젝트 디렉토리 생성
mkdir -p ~/apps
cd ~/apps

# Git 클론 (private repo인 경우 토큰 필요)
git clone https://github.com/YOUR_ORG/RDXL_OPS.git vibeops
cd vibeops
```

### 3.2 Python 환경 설정

```bash
# 가상환경 생성
python3.11 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 3.3 환경변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 편집
nano .env
```

```env
# .env 내용
# ===== Server =====
HOST=0.0.0.0
PORT=8000
DEBUG=false

# ===== Database =====
DATABASE_PATH=/home/vibeops/apps/vibeops/data/vibeops.db

# ===== Security =====
SECRET_KEY=your-super-secret-key-change-this

# ===== Douzone =====
DOUZONE_USERNAME=your_username
DOUZONE_PASSWORD=your_password

# ===== Slack =====
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx

# ===== Claude =====
ANTHROPIC_API_KEY=your_api_key
```

### 3.4 데이터베이스 초기화

```bash
# 데이터 디렉토리 생성
mkdir -p data

# DB 초기화 스크립트 실행
python backend/init_db.py
```

---

## 4. Tmux 설정

### 4.1 Tmux 세션 생성

```bash
# 새 세션 생성
tmux new-session -d -s vibeops

# 윈도우 생성
tmux new-window -t vibeops -n pm          # PM Agent
tmux new-window -t vibeops -n douzone     # Douzone Agent
tmux new-window -t vibeops -n news        # News Agent

# 세션 확인
tmux list-windows -t vibeops
```

### 4.2 Tmux 자동 시작 설정

```bash
# systemd 서비스 파일 생성
sudo nano /etc/systemd/system/vibeops-tmux.service
```

```ini
[Unit]
Description=VibeOps Tmux Session
After=network.target

[Service]
Type=forking
User=vibeops
ExecStart=/usr/bin/tmux new-session -d -s vibeops
ExecStop=/usr/bin/tmux kill-session -t vibeops
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable vibeops-tmux
sudo systemctl start vibeops-tmux
```

---

## 5. FastAPI 서버 설정

### 5.1 Systemd 서비스

```bash
# 서비스 파일 생성
sudo nano /etc/systemd/system/vibeops-api.service
```

```ini
[Unit]
Description=VibeOps FastAPI Server
After=network.target vibeops-tmux.service

[Service]
User=vibeops
WorkingDirectory=/home/vibeops/apps/vibeops
Environment="PATH=/home/vibeops/apps/vibeops/venv/bin"
ExecStart=/home/vibeops/apps/vibeops/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable vibeops-api
sudo systemctl start vibeops-api

# 상태 확인
sudo systemctl status vibeops-api
```

---

## 6. Nginx 리버스 프록시

### 6.1 Nginx 설정

```bash
# 설정 파일 생성
sudo nano /etc/nginx/sites-available/vibeops
```

```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    # Frontend (Static Files)
    location / {
        root /home/vibeops/apps/vibeops/frontend;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket for Bridge
    location /bridge/ws/ {
        proxy_pass http://127.0.0.1:8000/bridge/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

```bash
# 심볼릭 링크 생성
sudo ln -s /etc/nginx/sites-available/vibeops /etc/nginx/sites-enabled/

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

### 6.2 SSL 설정 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt install -y certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d YOUR_DOMAIN

# 자동 갱신 테스트
sudo certbot renew --dry-run
```

---

## 7. 모니터링 설정

### 7.1 로그 확인

```bash
# FastAPI 로그
sudo journalctl -u vibeops-api -f

# Nginx 로그
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Tmux 세션 접속
tmux attach -t vibeops
```

### 7.2 헬스체크 스크립트

```bash
# scripts/healthcheck.sh
#!/bin/bash

# API 헬스체크
curl -s http://localhost:8000/health || echo "API is down!"

# Tmux 세션 확인
tmux has-session -t vibeops 2>/dev/null || echo "Tmux session is down!"
```

---

## 8. 배포 체크리스트

### 8.1 초기 배포

- [ ] Droplet 생성 및 SSH 접속
- [ ] 기본 보안 설정 (방화벽, 사용자)
- [ ] 필수 패키지 설치
- [ ] 프로젝트 클론
- [ ] Python 환경 설정
- [ ] 환경변수 설정
- [ ] DB 초기화
- [ ] Tmux 세션 설정
- [ ] FastAPI 서비스 설정
- [ ] Nginx 설정
- [ ] SSL 설정

### 8.2 업데이트 배포

```bash
# 1. 코드 업데이트
cd ~/apps/vibeops
git pull origin main

# 2. 의존성 업데이트 (필요시)
source venv/bin/activate
pip install -r backend/requirements.txt

# 3. 서비스 재시작
sudo systemctl restart vibeops-api

# 4. 상태 확인
sudo systemctl status vibeops-api
curl http://localhost:8000/health
```

---

## 9. 백업

### 9.1 자동 백업 스크립트

```bash
# scripts/backup.sh
#!/bin/bash

BACKUP_DIR="/home/vibeops/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# 데이터베이스 백업
cp /home/vibeops/apps/vibeops/data/vibeops.db "$BACKUP_DIR/vibeops_$DATE.db"

# 오래된 백업 삭제 (7일 이상)
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
```

```bash
# crontab 등록 (매일 새벽 3시)
crontab -e
# 0 3 * * * /home/vibeops/apps/vibeops/scripts/backup.sh
```

---

*Last Updated: 2026-02-10*
