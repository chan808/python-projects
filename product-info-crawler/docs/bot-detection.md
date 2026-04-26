# 봇 탐지 대응

## 감지 대상

Akamai, Cloudflare, Imperva, DataDome, reCAPTCHA, hCaptcha 등

## 현재 적용된 우회 방법

- **undetected-chromedriver** (UC 모드) — ChromeDriver 감지 우회
- **headless 비활성화** — 헤드리스 모드는 Akamai 탐지 확률을 크게 높임
- **stealth 라이브러리 미사용** — 최신 Akamai가 selenium-stealth의 중복 설정을 역으로 감지함
- **랜덤 지연** — 카테고리 간 `inter_category_delay_sec × random.uniform(0.8, 1.5)`
- **인간형 스크롤** — `human_scroll()`: 소단위 분할 스크롤 + 미세 대기

## 차단 감지 종류 (`_detect_block_reason()`)

| 감지값 | 의미 |
|---|---|
| `akamai_access_denied` | Akamai WAF 차단 |
| `captcha_challenge` | reCAPTCHA / hCaptcha / Cloudflare Turnstile |
| `cloudflare_challenge` | Cloudflare JS 챌린지 |
| `cloudflare_wait` | Cloudflare 대기 페이지 |
| `http_403_forbidden` | 일반 403 |
| `advanced_bot_shield` | Distil / Imperva / DataDome |

차단 감지 시 `tmp_debug/{brand_id}/` 에 HTML 스냅샷 저장 후 `RuntimeError` 발생.

## 차단 발생 시 대처

1. `tmp_debug/{brand_id}/*.html` 파일을 브라우저로 열어 차단 화면 확인
2. `inter_category_delay_sec` 값을 올리거나 수동으로 브라우저를 조작해 쿠키 확보 후 재시도
3. 브랜드 사이트에서 수동 접속 후 CAPTCHA 통과 → 같은 Chrome 프로필로 크롤러 재실행 시도
