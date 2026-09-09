import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ==================================================
# 1. 기본 화면 설정
# ==================================================

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.caption("영화관입장권통합전산망(KOBIS) 일일 박스오피스")


# ==================================================
# 2. 한국 시간 기준 날짜 설정
# ==================================================
# 서버가 한국에 있지 않을 수 있기 때문에
# 반드시 한국 시간(KST)을 기준으로 오늘 날짜를 계산합니다.

kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()
yesterday = today_kst - timedelta(days=1)


# ==================================================
# 3. 달력에서 조회 날짜 선택
# ==================================================
# 가장 최근에 조회할 수 있는 날짜는 '어제'입니다.
# 따라서 오늘 날짜 이후는 선택할 수 없게 합니다.

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)

# KOBIS API에서 사용하는 YYYYMMDD 형식으로 변환
target_date = selected_date.strftime("%Y%m%d")

st.info(
    f"조회 날짜: {selected_date.strftime('%Y년 %m월 %d일')}"
)


# ==================================================
# 4. KOBIS API 호출 함수
# ==================================================
# 같은 날짜를 다시 조회하면 1시간 동안 저장된 결과를 사용합니다.
#
# target_dt가 함수의 입력값이기 때문에
# 날짜가 달라지면 해당 날짜의 데이터를 새로 가져옵니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # 인증키는 Streamlit Cloud의 Secrets에서 가져옵니다.
    # 실제 인증키를 코드에 직접 적지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    url = (
        "https://www.kobis.or.kr/kobisopenapi/"
        "webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        # JSON 데이터로 변환합니다.
        return response.json()

    except requests.exceptions.RequestException as e:
        return {
            "error": f"KOBIS API 요청에 실패했습니다.\n\n{e}"
        }

    except ValueError:
        return {
            "error": "KOBIS API가 올바른 JSON 데이터를 반환하지 않았습니다."
        }


# ==================================================
# 5. API에서 데이터 가져오기
# ==================================================

data = get_boxoffice(target_date)


# ==================================================
# 6. API 요청 자체가 실패한 경우
# ==================================================

if "error" in data:
    st.error("박스오피스 데이터를 가져오지 못했습니다.")

    st.warning(
        "다음 사항을 확인해 주세요.\n\n"
        "• Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지\n"
        "• KOBIS 인증키가 정확한지\n"
        "• 인증키가 아직 유효한지\n"
        "• 인터넷 연결 및 KOBIS API 서버 상태\n"
        "• 잠시 후 다시 실행해 보기"
    )

    st.stop()


# ==================================================
# 7. KOBIS의 faultInfo 확인
# ==================================================
# KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
# 따라서 faultInfo가 있는지 따로 확인해야 합니다.

if "faultInfo" in data:
    fault_info = data["faultInfo"]

    st.error("KOBIS API에서 오류를 반환했습니다.")

    if isinstance(fault_info, dict):
        error_message = (
            fault_info.get("message")
            or fault_info.get("error")
            or fault_info.get("faultstring")
            or str(fault_info)
        )

        st.write(f"오류 내용: {error_message}")

    else:
        st.write(f"오류 내용: {fault_info}")

    st.warning(
        "다음 사항을 확인해 주세요.\n\n"
        "• Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지\n"
        "• KOBIS 인증키가 정확한지\n"
        "• 인증키가 아직 유효한지\n"
        "• KOBIS Open API 이용에 문제가 없는지"
    )

    st.stop()


# ==================================================
# 8. 박스오피스 결과 가져오기
# ==================================================

boxoffice_result = data.get("boxOfficeResult")

if not boxoffice_result:
    st.error("KOBIS에서 박스오피스 결과를 받지 못했습니다.")

    st.warning(
        "KOBIS API의 응답 구조를 확인하거나 "
        "잠시 후 다시 실행해 주세요."
    )

    st.stop()


movie_list = boxoffice_result.get("dailyBoxOfficeList", [])


# ==================================================
# 9. 영화 목록이 없는 경우
# ==================================================
# 선택한 날짜에 영화 목록이 없으면
# 아직 해당 날짜의 박스오피스가 집계되지 않은 것으로 안내합니다.

if not movie_list:
    st.warning("📊 그날은 아직 집계 전입니다.")

    st.info(
        "선택한 날짜의 박스오피스 데이터가 아직 제공되지 않았습니다. "
        "다른 날짜를 선택하거나 집계가 완료된 후 다시 확인해 주세요."
    )

    st.stop()


# ==================================================
# 10. 숫자 데이터 변환
# ==================================================
# KOBIS API에서는 rank, audiCnt, audiAcc, scrnCnt,
# rankInten 등의 값이 문자열로 전달됩니다.
#
# 그래프와 정렬에 제대로 사용하기 위해 숫자로 변환합니다.

movies = []

for movie in movie_list:
    try:
        rank = int(movie.get("rank", 0))
        rank_inten = int(movie.get("rankInten", 0))
        audi_cnt = int(movie.get("audiCnt", 0))
        audi_acc = int(movie.get("audiAcc", 0))
        scrn_cnt = int(movie.get("scrnCnt", 0))

        movie_name = movie.get("movieNm", "")
        open_date = movie.get("openDt", "")

        # 누적관객이 100만 명을 넘은 영화에는 트로피 표시
        if audi_acc > 1_000_000:
            display_name = f"🏆 {movie_name}"
        else:
            display_name = movie_name

        movies.append({
            "순위": rank,
            "순위변동": rank_inten,
            "영화명": display_name,
            "개봉일": open_date,
            "관객수": audi_cnt,
            "누적관객": audi_acc,
            "스크린수": scrn_cnt
        })

    except (ValueError, TypeError):
        # 숫자로 변환할 수 없는 영화 데이터가 있으면
        # 해당 데이터는 건너뜁니다.
        continue


# 모든 영화 데이터가 변환에 실패한 경우
if not movies:
    st.warning(
        "영화 데이터는 받았지만 숫자 데이터를 정상적으로 "
        "변환하지 못했습니다. KOBIS API 응답을 확인해 주세요."
    )

    st.stop()


# ==================================================
# 11. 순위 기준으로 정렬
# ==================================================

movies.sort(key=lambda x: x["순위"])


# ==================================================
# 12. 1위 영화
# ==================================================

first_movie = movies[0]

st.subheader("🏆 1위 영화")

st.markdown(f"## {first_movie['영화명']}")


# ==================================================
# 13. 1위 영화의 주요 지표 카드
# ==================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "관객수",
        f"{first_movie['관객수']:,}명"
    )

with col2:
    st.metric(
        "누적관객",
        f"{first_movie['누적관객']:,}명"
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['스크린수']:,}개"
    )


# ==================================================
# 14. 관객수 상위 5편 그래프
# ==================================================

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬합니다.
top5 = sorted(
    movies,
    key=lambda x: x["관객수"],
    reverse=True
)[:5]


# 그래프에 사용할 데이터입니다.
# 영화명을 행 이름으로, 관객수를 값으로 사용합니다.
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top5
}

st.bar_chart(chart_data)


# ==================================================
# 15. 전체 박스오피스 표
# ==================================================

st.subheader("🎬 전체 박스오피스")


display_movies = []

for movie in movies:

    # 전날 대비 순위가 올랐는지/내렸는지 확인합니다.
    rank_inten = movie["순위변동"]

    if rank_inten > 0:
        # 양수 = 순위 상승
        rank_change = f":red[🔺 {rank_inten}]"

    elif rank_inten < 0:
        # 음수 = 순위 하락
        # 화면에는 음수 값 대신 변화량의 크기를 보여줍니다.
        rank_change = f":blue[🔻 {abs(rank_inten)}]"

    else:
        # 순위 변화가 없으면 -
        rank_change = "-"

    display_movies.append({
        "순위": movie["순위"],
        "변동": rank_change,
        "영화명": movie["영화명"],
        "개봉일": movie["개봉일"],
        "관객수": f"{movie['관객수']:,}",
        "누적관객": f"{movie['누적관객']:,}",
        "스크린수": f"{movie['스크린수']:,}"
    })


st.markdown(
    "🔺 **빨간색** = 전날보다 순위 상승 · "
    "🔻 **파란색** = 전날보다 순위 하락"
)

st.dataframe(
    display_movies,
    use_container_width=True,
    hide_index=True
)


# ==================================================
# 16. 데이터 출처
# ==================================================

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) Open API"
)
