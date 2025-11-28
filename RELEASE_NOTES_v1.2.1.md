# FLAMEHAVEN FileSearch v1.2.1 (2025-11-27)

## Highlights
- Admin IAM hardening: API 키는 `admin` 퍼미션이 필요하며, OIDC(HS256) 기반 토큰 검증 훅 추가 (`FLAMEHAVEN_IAM_PROVIDER=oidc`, `FLAMEHAVEN_OIDC_*`).
- 캐시 관리 API: `/api/admin/cache/stats`, `/api/admin/cache/flush` (관리자 전용) 추가.
- Metrics 확장: `/metrics` 응답에 cache/health 상태와 Prometheus 요약(최근 60s/300s 요청/에러 카운트, 히트/미스, 레이트리밋 초과) 포함.
- 프런트 대시보드: cache/metrics 페이지가 백엔드 엔드포인트와 연결됨; upload/admin 페이지는 토큰 입력 필드 제공.

## Breaking/Behavior Changes
- 기존 `admin` 퍼미션이 없는 API 키로 admin 라우트 호출 시 403 반환.
- 새로 발급되는 키 기본 퍼미션에 `admin` 포함.

## Configuration
- 필수: `FLAMEHAVEN_ADMIN_KEY`, `FLAMEHAVEN_ENC_KEY` (32-byte base64, AES-256-GCM).
- 선택(OIDC): `FLAMEHAVEN_IAM_PROVIDER=oidc`, `FLAMEHAVEN_OIDC_SECRET` (+ `..._ISSUER`, `..._AUDIENCE`).

## Testing
- 새 테스트: `tests/test_admin_cache.py` (관리자 캐시 stat/flush).
- 전체 스위트 실행 전 `pip install -r requirements.txt` 필요(특히 psutil, PyJWT).

## Docs
- README/SECURITY 업데이트: admin 퍼미션 요구, ENC/OIDC 환경 변수 추가.

