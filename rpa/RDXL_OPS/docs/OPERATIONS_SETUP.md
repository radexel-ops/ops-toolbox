# VibeOps 운영 안정화 문서

**작성일**: 2026-02-10
**서버**: 167.71.211.14 (DigitalOcean Droplet, Ubuntu 24.04)
**상태**: 배포 완료, Claude Code 연동 성공

---

## 1. 서버 현황

| 항목 | 값 |
|------|-----|
| IP | 167.71.211.14 |
| OS | Ubuntu 24.04 LTS |
| RAM | 4GB |
| Disk | 77GB (3.2GB 사용) |
| 사용자 | vibeops |
| Python | 3.12 |
| Node.js | 20.x |
| Claude Code | 2.1.38 |

---

## 2. 보안 설정

### 2.1 UFW 방화벽
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

**허용 포트:**
- 22 (SSH)
- 80 (HTTP)
- 443 (HTTPS)

### 2.2 Fail2ban (SSH 브루트포스 방지)
```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 3. 로그 관리

### 3.1 VibeOps Logrotate 설정
파일: `/etc/logrotate.d/vibeops`
```
/home/vibeops/vibeops/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 vibeops vibeops
}
```

### 3.2 Journald 크기 제한
```bash
sudo sed -i 's/#SystemMaxUse=/SystemMaxUse=500M/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

---

## 4. 자동 백업

### 4.1 백업 스크립트
파일: `/home/vibeops/vibeops/scripts/backup.sh`
- 매일 오전 3시 실행
- SQLite DB 백업
- 설정 파일 백업
- 7일 이상 된 백업 자동 삭제

### 4.2 Crontab
```
0 3 * * * /home/vibeops/vibeops/scripts/backup.sh >> /home/vibeops/vibeops/logs/backup.log 2>&1
```

---

## 5. 헬스 모니터링

### 5.1 헬스체크 스크립트
파일: `/home/vibeops/vibeops/scripts/healthcheck.sh`
- 5분마다 실행
- HTTP 200 아니면 서비스 자동 재시작
- 로그 기록

### 5.2 Crontab
```
*/5 * * * * /home/vibeops/vibeops/scripts/healthcheck.sh
```

---

## 6. Systemd 서비스

### 6.1 vibeops-api.service
```ini
[Unit]
Description=VibeOps API Server
After=network.target

[Service]
User=vibeops
Group=vibeops
WorkingDirectory=/home/vibeops/vibeops/backend
Environment="PATH=/home/vibeops/vibeops/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="HOME=/home/vibeops"
EnvironmentFile=/home/vibeops/vibeops/.env
ExecStart=/home/vibeops/vibeops/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5
MemoryMax=2G
CPUQuota=150%

[Install]
WantedBy=multi-user.target
```

---

## 7. 디렉토리 구조

```
/home/vibeops/vibeops/
├── backend/           # FastAPI 백엔드
├── frontend/          # 웹 프론트엔드
├── data/              # SQLite DB
├── logs/              # 애플리케이션 로그
├── scripts/           # 운영 스크립트
│   ├── backup.sh
│   └── healthcheck.sh
├── teams/             # 팀별 작업 디렉토리
└── .env               # 환경변수

/backup/vibeops/       # 백업 저장소
```

---

## 8. 운영 명령어

### 서비스 관리
```bash
# 상태 확인
sudo systemctl status vibeops-api

# 재시작
sudo systemctl restart vibeops-api

# 로그 확인
sudo journalctl -u vibeops-api -f
```

### 수동 백업
```bash
/home/vibeops/vibeops/scripts/backup.sh
ls -la /backup/vibeops/
```

### 헬스체크
```bash
curl http://localhost:8000/health
```

---

## 9. 장애 대응

### 서비스 다운 시
1. 로그 확인: `sudo journalctl -u vibeops-api -n 100`
2. 서비스 재시작: `sudo systemctl restart vibeops-api`
3. 여전히 실패 시: 에러 로그 분석

### 디스크 부족 시
1. 로그 정리: `sudo journalctl --vacuum-size=100M`
2. 백업 정리: `find /backup/vibeops -mtime +3 -delete`

---

## 10. 외부 모니터링 (선택)

### UptimeRobot (무료)
- URL: http://167.71.211.14/health
- 간격: 5분
- 알림: 이메일

### Sentry (무료 계층)
- 에러 추적 및 알림
- Python SDK 연동

---

*문서 최종 업데이트: 2026-02-10*
