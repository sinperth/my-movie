import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 페이지 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.write("한국 시간 기준 어제의 일일 박스오피스를 보여 줍니다.")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# --------------------------------------------------
# 배포 서버가 한국 시간이 아닐 수도 있기 때문에
# 서버의 현재 시간 대신 한국 시간(Asia/Seoul)을 사용합니다.

KST = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(KST).date()
yesterday_kst = today_kst - timedelta(days=1)

# KOBIS API에서 사용하는 날짜 형식: YYYYMMDD
target_date = yesterday_kst.strftime("%Y%m%d")

# 화면에 보여 줄 날짜
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 3. KOBIS API 주소
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# 4. KOBIS API에서 데이터를 가져오는 함수
# --------------------------------------------------
# @st.cache_data를 사용하면 같은 날짜의 결과를
# 일정 시간 동안 기억해서 API를 계속 호출하지 않습니다.
#
# ttl=3600 → 1시간 동안 캐시 유지

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # Streamlit Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 적지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다. "
                "Streamlit Cloud의 Secrets에 KOBIS_KEY가 "
                "등록되어 있는지 확인하세요."
            ),
            "data": None
        }

    # API 요청에 필요한 값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생했는지 확인합니다.
        response.raise_for_status()

        # JSON 형태의 응답을 읽습니다.
        result = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API에 접속하지 못했습니다.\n\n"
                "인터넷 연결이나 KOBIS API 주소를 확인하세요.\n\n"
                f"오류 내용: {e}"
            ),
            "data": None
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API의 응답을 JSON으로 읽지 못했습니다. "
                "API 서버 상태를 확인하세요."
            ),
            "data": None
        }

    # --------------------------------------------------
    # 5. 인증키 오류 확인
    # --------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 직접 확인해야 합니다.

    if "faultInfo" in result:
        fault_info = result["faultInfo"]

        fault_code = fault_info.get("faultCode", "알 수 없음")
        fault_string = fault_info.get(
            "faultString",
            "API에서 오류가 발생했습니다."
        )

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault_code}\n\n"
                f"오류 내용: {fault_string}\n\n"
                "KOBIS 인증키가 정확한지, "
                "API 사용 설정이 되어 있는지 확인하세요."
            ),
            "data": None
        }

    # --------------------------------------------------
    # 6. 박스오피스 결과가 있는지 확인
    # --------------------------------------------------

    boxoffice_result = result.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "KOBIS 응답에 boxOfficeResult가 없습니다. "
                "조회 날짜와 KOBIS API 상태를 확인하세요."
            ),
            "data": None
        }

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{display_date}의 영화 목록이 비어 있습니다.\n\n"
                "KOBIS에서 해당 날짜의 박스오피스가 아직 집계되지 않았거나, "
                "조회 날짜에 데이터가 없는지 확인하세요."
            ),
            "data": None
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# --------------------------------------------------
# 7. API 호출
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 8. API 오류 처리
# --------------------------------------------------

if not result["success"]:
    st.error(result["message"])
    st.info(
        "확인할 것: KOBIS_KEY 설정 → KOBIS API 상태 → "
        "조회 날짜의 박스오피스 집계 여부"
    )
    st.stop()


# --------------------------------------------------
# 9. 영화 데이터를 DataFrame으로 변환
# --------------------------------------------------

movie_list = result["data"]

df = pd.DataFrame(movie_list)


# --------------------------------------------------
# 10. 숫자로 변환
# --------------------------------------------------
# KOBIS API에서는 rank, audiCnt 등의 값도 문자열로 옵니다.
# 그래프와 정렬에 제대로 사용하기 위해 숫자로 변환합니다.

number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in number_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).astype(int)


# --------------------------------------------------
# 11. 1위 영화 정보
# --------------------------------------------------

# rank를 기준으로 다시 정렬합니다.
df = df.sort_values("rank").reset_index(drop=True)

first_movie = df.iloc[0]


# --------------------------------------------------
# 12. 날짜와 영화 수 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date}")

st.write(
    f"총 **{len(df)}편**의 영화가 집계되었습니다."
)


# --------------------------------------------------
# 13. 1위 영화의 주요 지표 카드
# --------------------------------------------------

st.subheader(f"🏆 1위: {first_movie['movieNm']}")

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        label="어제 관객수",
        value=f"{first_movie['audiCnt']:,}명"
    )

with card2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명"
    )

with card3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개"
    )


# --------------------------------------------------
# 14. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .copy()
)

# 영화 이름과 관객수를 그래프로 사용합니다.
chart = (
    alt.Chart(top5)
    .mark_bar()
    .encode(
        x=alt.X(
            "audiCnt:Q",
            title="관객수",
            axis=alt.Axis(format=",")
        ),
        y=alt.Y(
            "movieNm:N",
            title="영화명",
            sort="-x"
        ),
        tooltip=[
            alt.Tooltip("movieNm:N", title="영화명"),
            alt.Tooltip(
                "audiCnt:Q",
                title="관객수",
                format=","
            )
        ]
    )
    .properties(height=300)
)

st.altair_chart(
    chart,
    use_container_width=True
)


# --------------------------------------------------
# 15. 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

# 필요한 열만 골라서 화면에 표시합니다.
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 사용자가 보기 편하도록 열 이름을 한글로 바꿉니다.
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 숫자에 천 단위 쉼표를 표시합니다.
st.dataframe(
    table_df.style.format({
        "관객수": "{:,}",
        "누적관객": "{:,}",
        "스크린수": "{:,}"
    }),
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 16. 데이터 출처 안내
# --------------------------------------------------

st.caption(b
    f"데이터 출처: KOBIS 영화관입장권통합전산망 · "
    f"조회 날짜: {display_date}"
)
