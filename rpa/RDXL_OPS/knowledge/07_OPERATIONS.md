# 07. Operations & Security - VibeOps

> **문서 목적**: 운영, 보안, 모니터링 가이드를 정의합니다.

---

## 1. 운영 개요

### 1.1 서비스 구성

| 서비스 | 설명 | 포트 |
|--------|------|------|
| Nginx | 리버스 프록시 | 80, 443 |
| FastAPI | Backend API | 8000 |
| Tmux | 에이전트 세션 | - |
| SQLite | 데이터베이스 | - |

### 1.2 서비스 관리 명령어

```bash
# 서비스 상태 확인
sudo systemctl status vibeops-api
sudo systemctl status vibeops-tmux
sudo systemctl status nginx

# 서비스 재시작
sudo systemctl restart vibeops-api

# 로그 확인
sudo journalctl -u vibeops-api -f
```

---

## 2. 모니터링

### 2.1 시스템 모니터링

```bash
# 리소스 사용량
htop

# 디스크 사용량
df -h

# 메모리 사용량
free -m

# 프로세스 확인
ps aux | grep python
ps aux | grep tmux
```

### 2.2 애플리케이션 모니터링

```bash
# API 헬스체크
curl http://localhost:8000/health

# 응답 예시
{
    "status": "healthy",
    "timestamp": "2026-02-10T14:30:00Z",
    "services": {
        "database": "ok",
        "tmux": "ok",
        "agents": {
            "pm": "running",
            "douzone": "running",
            "news": "stopped"
        }
    }
}
```

### 2.3 로그 관리

| 로그 | 경로 | 설명 |
|------|------|------|
| API 로그 | journalctl -u vibeops-api | FastAPI 서버 로그 |
| Nginx 로그 | /var/log/nginx/access.log | HTTP 요청 로그 |
| 에이전트 로그 | ~/apps/vibeops/logs/ | 에이전트별 로그 |

```bash
# 로그 로테이션 설정
# /etc/logrotate.d/vibeops

/home/vibeops/apps/vibeops/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

---

## 3. 보안

### 3.1 서버 보안

#### 방화벽 (UFW)
```bash
# 현재 규칙 확인
sudo ufw status

# 필수 포트만 허용
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

#### SSH 보안
```bash
# /etc/ssh/sshd_config

# Root 로그인 비활성화
PermitRootLogin no

# 비밀번호 인증 비활성화 (키 인증만)
PasswordAuthentication no

# 최대 인증 시도 횟수
MaxAuthTries 3
```

### 3.2 애플리케이션 보안

#### 환경변수 관리
```bash
# 민감 정보는 반드시 .env 파일에
# .env 파일 권한 제한
chmod 600 .env

# Git에서 제외 확인
cat .gitignore | grep .env
```

#### API 보안
```python
# CORS 설정
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # 특정 도메인만
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Rate Limiting
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.get("/api/agents")
@limiter.limit("60/minute")
async def list_agents():
    pass
```

### 3.3 데이터 보안

#### 데이터베이스 백업
```bash
# 일일 백업 스크립트
#!/bin/bash
# scripts/backup_db.sh

BACKUP_DIR="/home/vibeops/backups"
DB_PATH="/home/vibeops/apps/vibeops/data/vibeops.db"
DATE=$(date +%Y%m%d_%H%M%S)

# SQLite 백업
sqlite3 $DB_PATH ".backup '$BACKUP_DIR/vibeops_$DATE.db'"

# 압축
gzip "$BACKUP_DIR/vibeops_$DATE.db"

# 7일 이상 된 백업 삭제
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
```

#### 민감 데이터 암호화
```python
# 비밀번호 해싱
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

---

## 4. 알림 설정

### 4.1 Slack 알림

```python
# services/notification_service.py

import httpx
import os

class NotificationService:
    def __init__(self):
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")

    async def send_alert(self, message: str, level: str = "info"):
        """슬랙 알림 전송"""
        emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
            "success": "✅"
        }.get(level, "📢")

        payload = {
            "text": f"{emoji} *[VibeOps]* {message}"
        }

        async with httpx.AsyncClient() as client:
            await client.post(self.slack_webhook, json=payload)

# 사용 예시
notification = NotificationService()
await notification.send_alert("에이전트 douzone 오류 발생", "error")
```

### 4.2 알림 트리거

| 이벤트 | 알림 레벨 | 설명 |
|--------|----------|------|
| 에이전트 시작 | info | 에이전트 시작됨 |
| 에이전트 오류 | error | 에이전트 실행 실패 |
| 작업 완료 | success | 스케줄 작업 완료 |
| 디스크 80% | warning | 디스크 용량 부족 |
| API 응답 지연 | warning | 응답 시간 3초 초과 |

---

## 5. 장애 대응

### 5.1 일반적인 문제 해결

#### API 서버 응답 없음
```bash
# 1. 서비스 상태 확인
sudo systemctl status vibeops-api

# 2. 로그 확인
sudo journalctl -u vibeops-api --since "10 minutes ago"

# 3. 포트 사용 확인
sudo lsof -i :8000

# 4. 서비스 재시작
sudo systemctl restart vibeops-api
```

#### Tmux 세션 없음
```bash
# 1. 세션 확인
tmux list-sessions

# 2. 세션 없으면 재생성
tmux new-session -d -s vibeops
tmux new-window -t vibeops -n pm
tmux new-window -t vibeops -n douzone
tmux new-window -t vibeops -n news
```

#### 디스크 용량 부족
```bash
# 1. 용량 확인
df -h

# 2. 큰 파일 찾기
du -sh /home/vibeops/apps/vibeops/* | sort -h

# 3. 불필요한 로그 삭제
find /home/vibeops/apps/vibeops/logs -name "*.log" -mtime +30 -delete

# 4. 오래된 백업 삭제
find /home/vibeops/backups -name "*.gz" -mtime +14 -delete
```

### 5.2 복구 절차

#### 데이터베이스 복구
```bash
# 1. 서비스 중지
sudo systemctl stop vibeops-api

# 2. 백업에서 복구
gunzip -c /home/vibeops/backups/vibeops_YYYYMMDD.db.gz > /home/vibeops/apps/vibeops/data/vibeops.db

# 3. 권한 설정
chown vibeops:vibeops /home/vibeops/apps/vibeops/data/vibeops.db

# 4. 서비스 시작
sudo systemctl start vibeops-api
```

---

## 6. 유지보수 체크리스트

### 6.1 일일 점검

- [ ] API 헬스체크 확인
- [ ] 에이전트 상태 확인
- [ ] 에러 로그 확인

### 6.2 주간 점검

- [ ] 디스크 용량 확인
- [ ] 백업 정상 동작 확인
- [ ] 보안 업데이트 확인

### 6.3 월간 점검

- [ ] 시스템 업데이트 적용
- [ ] 로그 정리
- [ ] 성능 모니터링 리뷰

---

*Last Updated: 2026-02-10*
