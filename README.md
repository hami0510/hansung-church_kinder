# 한성교회 유치부 관리 시스템

한성교회 유치부 교사들이 함께 쓰는 웹 관리 앱입니다.
아동·교사 명단, 일정, 주일 출석 보고, 심방·기도제목 요청, 공지사항을 한곳에서 관리합니다.

- **기술 구성**: Streamlit(화면) + Supabase(데이터 저장) + GitHub(코드 보관) + Streamlit Community Cloud(배포)
- **주소**: https://hansung-churchkinder.streamlit.app

---

## 주요 기능

| 메뉴 | 설명 | 사용 권한 |
|---|---|---|
| 홈 | 공지, 이번 주 생일, 월간 달력(날짜·일정 클릭 시 팝업) | 모두 |
| 공지사항 | 작성·수정·삭제, 상단 고정(📌) | 모두 |
| 일정 관리 | 일정 보기·등록·수정·삭제, 시간 지정, 일괄 삭제 | 모두 |
| 아동 명부 | 명단 조회·검색, 사진, 등록·수정·퇴원·삭제, CSV 내려받기 | 조회: 모두 / 변경·연락처: 관리자 |
| 교사·반 명단 | 반·부·반 번호별 명단, 등록·수정·삭제 | 조회: 모두 / 변경·연락처: 관리자 |
| 주일 출석 보고 | 교사 이름 검색 후 출석/불참/미정 제출, 토요일 12시 마감, 제출 현황 | 모두 |
| 심방 요청 | 교사가 요청 접수, 처리 상태 관리 | 요청: 모두 / 목록: 관리자 |
| 기도제목 요청 | 교사가 기도제목 접수, 상태 관리 | 요청: 모두 / 목록: 관리자 |
| 엑셀 업로드 | 아동·교사 명단 일괄 등록(미리보기·중복 확인) | 관리자 |
| 반 이동·진급 | 조이→해피→홀리→졸업 일괄 처리 | 관리자 |

> 권한 설정은 `utils/auth.py`에서 바꿀 수 있습니다.

---

## 폴더 구조

```
church-kinder/
├── app.py                  # 시작 파일 (메뉴, 관리자 로그인)
├── requirements.txt        # 필요한 패키지 목록
├── .streamlit/
│   └── config.toml         # 테마 색상
├── utils/
│   ├── auth.py             # 권한 설정
│   ├── db.py               # Supabase 읽기·쓰기·사진 처리
│   ├── ui.py               # 디자인(CSS), 카드·배너
│   ├── labels.py           # 반·부·반 번호 표시
│   ├── phone.py            # 연락처 자동 하이픈
│   ├── pick.py             # 이름 검색 선택
│   ├── birthdays.py        # 생일 계산
│   ├── notice_ui.py        # 공지 카드
│   └── notify.py           # 알림(텔레그램 연결 예정)
└── views/
    ├── home.py             # 홈
    ├── notices.py          # 공지사항
    ├── events.py           # 일정 관리
    ├── children.py         # 아동 명부
    ├── teachers.py         # 교사·반 명단
    ├── sunday_report.py    # 주일 출석 보고
    ├── visit_request.py    # 심방 요청
    ├── prayer_request.py   # 기도제목 요청
    ├── bulk_upload.py      # 엑셀 업로드
    └── promotion.py        # 반 이동·진급
```

---

## 반 구성

- **반**: 조이(5세) / 해피(6세) / 홀리(7세) / 새싹(새가족)
- **부**: 1부 / 2부 (교사는 "1·2부 모두" 선택 가능)
- **반 번호**: 1~5반

---

## 설정 방법

### 1. Supabase

1. [supabase.com](https://supabase.com)에서 프로젝트를 만듭니다.
2. SQL Editor에서 테이블을 만듭니다.
   `children`, `teachers`, `attendance`, `events`, `duties`, `visits`, `notices`, `sunday_reports`, `visit_requests`, `prayer_requests`
3. Storage에 **비공개** 버킷 `child-photos`를 만듭니다.
4. Project Settings → API Keys에서 **Project URL**과 **Secret key**(`sb_secret_...`)를 확인합니다.

### 2. Streamlit Secrets

Streamlit Community Cloud → 앱 → Settings → Secrets에 아래 형식으로 입력합니다.
**이 값은 GitHub 코드에 절대 적지 않습니다.**

```toml
[supabase]
url = "https://xxxxxxxx.supabase.co"
key = "sb_secret_..."

[auth]
admin_password = "관리자 비밀번호"
```

### 3. 배포

1. 이 저장소를 Streamlit Community Cloud에 연결합니다.
2. Main file path는 `app.py`로 지정합니다.
3. GitHub에서 파일을 수정하고 Commit하면 1~2분 안에 자동으로 반영됩니다.

---

## 관리자 로그인

- 앱 왼쪽 사이드바(휴대폰은 왼쪽 위 `≫`)의 **🔒 관리자 로그인**에 비밀번호를 입력합니다.
- 아동·교사 명부의 등록·수정·삭제, 연락처 열람, 엑셀 업로드, 반 이동·진급은 관리자만 할 수 있습니다.
- 비밀번호 변경: Streamlit Secrets의 `admin_password` 값을 바꾸고 저장합니다.

---

## 운영 안내

- **연말 진급**: 반 이동·진급 화면에서 백업 CSV를 먼저 내려받은 뒤 한 번만 실행합니다.
- **백업**: 아동 명부 화면의 CSV 다운로드로 한 달에 한 번 보관을 권장합니다.
- **Supabase 무료 플랜**: 약 1주일간 접속이 없으면 프로젝트가 일시정지됩니다. Supabase 대시보드에서 **Restore**를 누르면 복구됩니다.
- **Streamlit 무료 앱**: 한동안 접속이 없으면 잠듭니다. 처음 여는 사람이 "Yes, get this app back up!" 버튼을 누르면 됩니다.

---

## 개인정보 보호 안내

이 앱에는 **아동 이름, 사진, 생년월일, 보호자 연락처, 알레르기** 등 개인정보가 저장됩니다.

- 앱 주소는 **교사진에게만** 공유합니다.
- 정보 수집·이용에 대한 **보호자 동의**를 받고, 교회의 개인정보 처리 기준을 따릅니다.
- 비밀번호와 API 키는 **GitHub 코드에 적지 않고** Streamlit Secrets에만 보관합니다.
- 사진은 비공개 저장소에 두며, 1시간짜리 임시 주소로만 표시됩니다.
- 퇴원·졸업한 아동의 정보는 보관 기간을 정해 정기적으로 삭제합니다.

---

## 앞으로 할 일

- [ ] 아동 출석 체크 및 통계 (연속 결석 → 심방 요청 연결)
- [ ] 교사 출석 (월례회·교사대학·행사)
- [ ] 텔레그램 알림 (심방·기도제목 요청 접수 시)
- [ ] 교사별 개인 계정과 변경 기록
- [ ] 모바일 화면 다듬기

---

## 문의

관리 담당: 한성교회 유치부 (담당자 이름·연락처를 적어 주세요)
