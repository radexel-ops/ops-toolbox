# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치 (일부 패키지 빌드에 필요)
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 의존성 먼저 복사 (캐싱 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 업로드 폴더 생성
RUN mkdir -p uploads

# 포트 노출
EXPOSE 8000

# 실행 명령
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
