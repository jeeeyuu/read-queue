# ReadQueue (로컬 우선)

## 1. 런타임 요구사항 (Linux/WSL 우선)
ReadQueue는 Linux 기반 런타임 앱입니다.
- Linux: polling/ingestion을 직접 실행
- Windows: 반드시 WSL 내부에서 메인 런타임 실행
- Windows `.bat`는 WSL 런타임을 호출하는 트리거일 뿐, 독립 실행 런타임이 아닙니다.

## 2. 프로젝트 개요
ReadQueue는 여러 입력 경로에서 링크를 받아 메타데이터/요약을 생성해 Notion에 저장합니다.
워크플로우 UI는 Notion(상태, 읽음, 메모, 태그)입니다.
데스크톱 GUI나 웹 프론트엔드는 제공하지 않습니다.

## 3. 입력 모드
- Telegram bot 입력 (polling)
- 원클릭 로컬 클립보드 입력 (Windows/macOS/Linux/WSL)

두 모드는 동일한 공용 ingestion 파이프라인을 사용합니다.
- URL 추출/정규화
- 트래킹 파라미터 제거
- 중복 감지
- 메타데이터 추출
- OpenAI 한국어 제목 정리 + 1줄 요약
- 비링크 텍스트를 Notion `Note`로 저장
- Notion 기록

## 4. 최근 동작
- 다중 링크 안정 처리
  - 한 메시지에 여러 링크가 있으면 링크별로 개별 Notion 아이템 생성
  - 같은 입력 내 중복 링크는 첫 번째만 처리
- 공통 메모 처리
  - 같은 입력의 비링크 텍스트를 해당 입력의 모든 링크 `Note`에 공통 저장
- URL 파싱 강화
  - 괄호 포함 URL(`.../Function_(mathematics)`) 처리
  - 문장부호 래핑 제거 개선
- 메타데이터 실패 fallback
  - 메타데이터 실패/빈약 시 입력 텍스트를 OpenAI로 요약해 제목/요약 필드 보완
- 중복 링크 메모 append
  - 이미 존재하는 링크에 텍스트가 함께 오면 기존 `Note` 뒤에 줄바꿈으로 추가(덮어쓰기 없음)

## 5. 기능
- Telegram polling 수집 + 다중 링크 처리
- 생성형 launcher를 통한 클립보드 원클릭 전송
- 입력 경로 공통 파이프라인
- Notion 중복 방지 + 상태 워크플로우
- 구조화 로그 + retry/backoff

## 6. 사전 준비
- Python 3.11+
- OpenAI API 키
- Notion integration token + Notion DB
- Telegram bot token
- Windows 사용 시 WSL 설치

## 7. 설치
1. 의존성 설치
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```
2. 필수 설정 파일 생성
- `config/config.example.yaml` -> `config/config.yaml`
- `config/secrets.example.yaml` -> `config/secrets.yaml`
3. 실제 키/ID 입력
4. `config/secrets.yaml`은 git에 커밋하지 않음(`.gitignore`에 이미 제외)

## 8. Notion 설정
1. Notion 내부 integration 생성 후 API 키 복사
2. DB 생성 후 필수 속성 추가
3. **Add connections**로 DB를 integration과 연결
4. `config/config.yaml`에 DB ID 입력

### 필수 Notion 속성

| 속성명 | 타입 | 용도 |
|---|---|---|
| Title | title | 표시 제목 |
| URL | url | 정규화 원본 URL |
| Canonical URL | url | canonical URL |
| Domain | rich_text | 도메인 |
| Original Title | rich_text | 원문 제목 |
| Cleaned Title KO | rich_text | 정리된 한국어 제목 |
| Summary One Line KO | rich_text | 한국어 1줄 요약 |
| Status | select | Inbox/Queued/Reading/Done/Archived/Failed |
| Read | checkbox | 읽음 상태 |
| Note | rich_text | 사용자 메모(중복 append 포함) |
| Tags | multi_select | 태그 |
| Source | select | telegram:username / local / manual |
| Saved At | date | 저장 시각 |
| Telegram Message ID | rich_text | telegram 메시지 ID |
| Error Message | rich_text | 경고/실패 사유 |

## 9. Telegram 설정
1. `@BotFather`로 bot 생성
2. token을 `config/secrets.yaml`에 입력
3. bot과 채팅 시작
4. `config/secrets.yaml`에 chat_id 접근제어 설정
- `TELEGRAM_ALLOWED_CHAT_IDS`

접근제어 동작:
- 기본 정책은 **default deny**
- `TELEGRAM_ALLOWED_CHAT_IDS`가 비어 있으면 Telegram 입력은 전부 폐기
- 허용되지 않은 업데이트는 오프셋만 소비하고 즉시 폐기(응답/후처리 없음)
- 인가 전 단계에서 차단되므로 URL 추출/메타데이터/OpenAI/Notion 호출 없음

인가된 Telegram 메시지의 Notion `Source`:
- `telegram:username` 형식으로 저장 (예: `telegram:alice`)

## 10. 로컬 클립보드 전송
내부 스크립트:
```bash
python scripts/send_clipboard.py
```

클립보드 백엔드:
- Windows: `PowerShell Get-Clipboard`
- WSL: `powershell.exe -NoProfile -Command Get-Clipboard`
- macOS: `pbpaste`
- Linux: `wl-paste` -> `xclip` -> `xsel`

클립보드 비어 있음/백엔드 없음 시 non-zero 종료

## 11. 런처 생성
```bash
python scripts/generate_launchers.py
```

`config/config.yaml` 주요 항목:
- `launchers.windows_bat_output_path`
- `launchers.windows_pause_on_exit`
- `launchers.macos_command_output_path`
- `linux_runtime.run_root`, `linux_runtime.python_bin`, `linux_runtime.use_venv`, `linux_runtime.venv_path`

경로/venv 변경 시 런처 재생성 필요

## 12. 실행
### Telegram polling
```bash
python scripts/run_polling.py
```

### Windows 클립보드 예시
1. WSL 런타임 환경 준비(venv/config)
2. `python scripts/generate_launchers.py`
3. 생성된 `.bat` 더블클릭

### macOS 클립보드 예시
1. 런처 생성
2. `.command` 더블클릭

## 13. polling 가용성
Telegram 모드는 polling 기반이므로 프로세스가 살아있는 동안만 동작합니다.
- 로컬 PC를 계속 켜두고 `run_polling.py` 유지
- 또는 항상 켜진 서버/VM에 배포

중단되면 Telegram ingestion도 중단됩니다.

## 14. 트러블슈팅
- launcher 경로 오류: `launchers.windows_bat_output_path` 수정 후 재생성
- WSL 실행 불가: Windows에서 `wsl.exe` 동작 확인
- clipboard 백엔드 없음: Linux는 wl-paste/xclip/xsel 설치
- 런처가 잘못된 런타임을 가리킴: `linux_runtime.run_root` 확인 후 재생성
- 런타임 준비 미완료: venv/config/dependency 재확인
- Telegram이 계속 거절됨: `TELEGRAM_ALLOWED_CHAT_IDS` 값 확인
- Notion/OpenAI 오류: 키/DB 공유/속성명 확인

## 15. 테스트
```bash
pytest
```

## 16. 향후 개선
- Telegram webhook 모드
- richer article extraction
- batch import
- daily digest
- optional local cache

## English README
영문 문서는 [README_english.md](README_english.md)에서 확인할 수 있습니다.
