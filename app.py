import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from streamlit_autorefresh import st_autorefresh
from google.cloud.firestore_v1.base_query import FieldFilter
import numpy as np
import random
import time

st.set_page_config(initial_sidebar_state="collapsed")  # 사이드바를 기본 닫힘 상태로 설정

# Google Fonts에서 나눔 고딕 불러오기 및 적용
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Gothic&display=swap');

    * {
        font-family: 'Nanum Gothic', sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)

# PWA 관련 설정
st.markdown(
    """
    <link rel="manifest" href="manifest.json">
    <script>
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('service-worker.js').then(function() {
            console.log('Service Worker Registered');
        });
    }
    </script>
    """,
    unsafe_allow_html=True
)

# 페이지 상태를 세션 상태에 저장
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# 페이지 전환을 위한 함수 정의
def set_page(page_name):
    st.session_state.page = page_name

# Firebase 초기화 (한 번만 실행되도록)
@st.cache_resource
def initialize_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": st.secrets["gcp_service_account"]["type"],
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"].replace("\\n", "\n"),
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
            "token_uri": st.secrets["gcp_service_account"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
        })
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = initialize_firebase()

# Initialize session state for page navigation
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# Sample EP data for demonstration
EP_LIST = [f"EP_{i}" for i in range(1, 17)]

# 초기 데이터 생성 (EP별 데이터 샘플)
@st.cache_data
def initialize_data():
    data = {
        ep: pd.DataFrame({
            'timestamp': pd.date_range(start=datetime.now() - timedelta(hours=1), periods=30, freq='2S'),
            'flowRate': np.random.randint(10, 100, size=30)
        }) for ep in EP_LIST
    }
    return data

# Firestore에서 데이터 가져오기
def get_firestore_data():
    doc_ref = db.collection('Waterflow_data').document('realtime')
    doc = doc_ref.get()
    if doc.exists():
        return doc.to_dict()
    return None

# 데이터 업데이트 함수
def update_data(historical_data):
    firestore_data = get_firestore_data()
    if firestore_data:
        current_time = datetime.now()
        for ep, df in historical_data.items():
            if ep in firestore_data:
                flow_rate = firestore_data[ep].get('flowRate', 0)
                new_data = pd.DataFrame({'timestamp': [current_time], 'flowRate': [flow_rate]})
                historical_data[ep] = pd.concat([historical_data[ep], new_data]).reset_index(drop=True)
                
                # 최근 10분의 데이터만 유지
                historical_data[ep] = historical_data[ep][historical_data[ep]['timestamp'] > current_time - timedelta(minutes=10)]
    return historical_data

@st.cache_data
def create_graph(data, ep):
    fig = go.Figure()
    
    if not data.empty:
        fig.add_trace(go.Scatter(
            x=data['timestamp'], 
            y=data['flowRate'],
            mode='lines+markers',
            name=ep
        ))
    
    fig.update_layout(
        title=f'Flow Rate for {ep} over Time',
        xaxis_title='Time',
        yaxis_title='Flow Rate',
        height=300  # 그래프 높이 조정
    )
    
    return fig

def get_current_datetime():
    now = datetime.now()
    return now.strftime("%Y년 %m월 %d일 %H시 %M분")

def get_hourly_usage():
    return [100, 110, 120, 130, 140, 150, 160, 170, 180, 190,
            200, 210, 220, 230, 240, 250, 260, 270, 280, 290,
            300, 310, 320, 330]

def create_hourly_usage_graph(hourly_usage):
    if not isinstance(hourly_usage, (list, np.ndarray)) or len(hourly_usage) != 24:
        raise ValueError('hourly_usage must be a list or array of 24 values')

    now = datetime.now()
    current_hour = now.hour

    all_hours = [f'{i:02d}:00' for i in range(24)]

    # 현재 시간을 기준으로 10시간 데이터만 선택
    start_idx = (current_hour - 9) % 24
    visible_hours = [all_hours[(start_idx + i) % 24] for i in range(10)]
    visible_usage = [hourly_usage[(start_idx + i) % 24] for i in range(10)]

    # 10시간 데이터만으로 그래프 생성
    fig = go.Figure(data=[go.Bar(x=visible_hours, y=visible_usage)])
    fig.update_layout(
        title='최근 10시간의 사용량',
        xaxis_title='시간대',
        yaxis_title='사용량',
        height=400,
        width=800,
        xaxis_tickangle=-45,
    )

    # x축 설정
    fig.update_xaxes(
        type='category',
        categoryorder='array',
        categoryarray=visible_hours,
        fixedrange=False  # 스크롤 허용
    )

    return fig

# Example usage
hourly_data = [104, 89, 92, 123, 55, 50, 52, 89, 72, 61, 106, 140, 60, 108, 66, 91, 143, 142, 128, 121, 72, 137, 132, 51]
graph = create_hourly_usage_graph(hourly_data)

def calculate_daily_usage(hourly_usage):
    return sum(hourly_usage)

def calculate_estimated_bill(daily_usage, rate):
    return daily_usage * rate

# 기본 지역과 용도를 세션 상태에 초기화 (여기에 추가합니다)
if 'region' not in st.session_state:
    st.session_state.region = '서울'  # 기본값을 '서울'로 설정
if 'usage_type' not in st.session_state:
    st.session_state.usage_type = '가정용'  # 기본값을 '가정용'으로 설정

# 기존 홈 페이지 함수 수정 (autorefresh로 특정 요소만 갱신)
def home_page():
    st.title("REALTIME WATERFLOW DATA")

    # 데이터 초기화 (세션 상태에 데이터가 없을 경우 초기화)
    if 'historical_data' not in st.session_state:
        st.session_state.historical_data = initialize_data()

    # 실시간 수도 사용량 그래프만 리프레시
    total_flow_placeholder = st.empty()

    # 2초마다 실시간 수도 사용량 그래프 갱신
    st_autorefresh(interval=2000, key="flow_refresh")
    with total_flow_placeholder.container():
        display_total_flow()

    # 데이터 업데이트를 위한 빈 공간 설정
    usage_placeholder = st.empty()

    # 2초마다 사용량 및 요금 정보 갱신
    st_autorefresh(interval=2000, key="usage_refresh")
    with usage_placeholder.container():
        # 이번 달 사용량 및 요금 계산
        current_month_usage = calculate_current_month_usage()
        previous_month_usage = calculate_previous_month_usage()

        # 이번 달 요금 계산 (설정된 수도 요금, 하수도 요금, 물이용부담금 활용)
        current_month_fee = calculate_estimated_bill(current_month_usage, water_fees[st.session_state.region][st.session_state.usage_type]["상수도 요금"])

        # 데이터 표시
        st.subheader("USAGE")
        st.write(f"THIS MONTH USAGE: {current_month_usage / 30:.2f} L (Expectations)")
        st.write(f"THE PREVIOUS USAGE: {previous_month_usage:.2f} L")
        st.write(f"THIS MONTH FEE: {current_month_fee:.2f} WON")


# 실시간 수도 사용량 그래프 함수 수정
def display_total_flow():
    # 그래프만 새로고침하는 부분
    total_flow_placeholder = st.empty()

    # 데이터를 갱신
    update_data(st.session_state.historical_data)

    # 모든 EP의 실시간 데이터에서 가장 최신 데이터를 추출하여 합산
    total_flow = 0
    current_time = datetime.now()

    # EP 데이터에서 가장 최신 데이터를 가져와 합산
    for ep, data in st.session_state.historical_data.items():
        if not data.empty:
            # 각 EP별로 가장 최신의 flowRate를 추출
            latest_flow = data.iloc[-1]['flowRate']
            total_flow += latest_flow

    # 최신 데이터로 게이지 차트 업데이트
    with total_flow_placeholder:
        if total_flow > 0:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=total_flow,
                gauge={'axis': {'range': [None, max(500, total_flow)]}},
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "TOTAL GROUP REALTIME USAGE(L/MIN)"}
            ))
        else:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=0,
                gauge={'axis': {'range': [None, 100]}},
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "TOTAL GROUP REALTIME USAGE (L/MIN) - NO DATA"}
            ))

        # config 옵션 추가
        st.plotly_chart(fig, use_container_width=True, config={'staticPlot': False})

    # 마지막 업데이트 시간 표시
    st.write(f"LAST UPDATE: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

# 이번 달 사용량 계산 함수
def calculate_current_month_usage():
    total_flow = 0
    current_time = datetime.now()
    current_month = current_time.month

    for ep, data in st.session_state.historical_data.items():
        # 이번 달 데이터만 계산
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        current_month_data = data[data['timestamp'].dt.month == current_month]
        if not current_month_data.empty:
            total_flow += current_month_data['flowRate'].sum()

    return total_flow

# 전월 사용량 계산 함수
def calculate_previous_month_usage():
    total_flow = 0
    current_time = datetime.now()
    previous_month = (current_time.month - 1) if current_time.month > 1 else 12

    for ep, data in st.session_state.historical_data.items():
        # 전월 데이터만 계산
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        previous_month_data = data[data['timestamp'].dt.month == previous_month]
        if not previous_month_data.empty:
            total_flow += previous_month_data['flowRate'].sum()

    return total_flow

# 갱신 시간 설정 및 데이터 갱신 함수
def update_data(historical_data):
    # 모든 EP 데이터에 새로운 2초 단위 데이터를 추가
    for ep in st.session_state.historical_data:
        # 새로운 데이터 추가
        new_row = pd.DataFrame({
            'timestamp': [datetime.now()],
            'flowRate': [random.randint(10, 100)]  # random 모듈을 사용해 임의의 데이터 생성
        })
        st.session_state.historical_data[ep] = pd.concat([st.session_state.historical_data[ep], new_row], ignore_index=True)

        # 10분 전 데이터까지만 유지 (필요 시 수정 가능)
        st.session_state.historical_data[ep] = st.session_state.historical_data[ep][
            st.session_state.historical_data[ep]['timestamp'] > datetime.now() - timedelta(minutes=10)
        ]

def realtime_data_page():
    st.title("REALTIME WATERFLOW DATA")

    # 데이터 초기화
    if 'historical_data' not in st.session_state:
        st.session_state.historical_data = initialize_data()

    # 갱신 시간 설정 (2초 ~ 10초)
    refresh_interval = st.sidebar.slider("데이터 갱신 시간 (초)", 2, 10, 2)
    
    # 자동 갱신 설정
    st_autorefresh(interval=refresh_interval * 1000, key="data_refresh")

    # 2초마다 데이터 갱신
    update_data(st.session_state.historical_data)  # historical_data를 인자로 넘김

    selected_eps = []  # selected_eps 초기화
    display_option = "디바이스"  # 기본값으로 display_option을 초기화

    # 사이드바에서 그룹 또는 개별 EP 선택
    with st.sidebar:
        st.header("기기설정")
        
        # 그룹 선택
        if 'groups' in st.session_state and st.session_state.groups:  # 그룹이 있는지 확인
            available_groups = list(st.session_state.groups.keys())
            display_option = st.radio("", ["그룹", "디바이스"])

            if display_option == "그룹":
                selected_group = st.selectbox("그룹 선택", available_groups)
                if selected_group:
                    selected_eps = st.session_state.groups[selected_group]
            elif display_option == "디바이스":
                selected_eps = st.multiselect("디바이스 선택", options=EP_LIST, default=EP_LIST[:5])
        else:
            st.write("그룹이 없습니다. 설정에서 만들어주세요.")
            selected_eps = st.multiselect("디바이스", options=EP_LIST, default=EP_LIST[:5])  # 그룹이 없을 경우에도 선택 가능하게 함
    
    # 본 페이지에 그래프 표시
    if display_option == "그룹" and selected_eps:
        # 그룹 데이터 합산 및 시각화
        combined_data = calculate_group_data(selected_eps, st.session_state.historical_data)

        # 그룹 합산 그래프 표시
        fig = go.Figure()
        if combined_data is not None:
            fig.add_trace(go.Scatter(
                x=combined_data['timestamp'], 
                y=combined_data['flowRate'],
                mode='lines+markers',
                name=f"{selected_group} GROUP TOTAL DATA"
            ))

        fig.update_layout(
            title=f'{selected_group} FLOW RATE DATA',
            xaxis=dict(type='date', tickformat='%H:%M:%S'),  # 2초 단위로 시간 형식 지정
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

    elif display_option == "디바이스" and selected_eps:
        # 선택된 각 EP에 대한 그래프 개별 표시
        for ep in selected_eps:
            ep_data = st.session_state.historical_data[ep]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=ep_data['timestamp'], 
                y=ep_data['flowRate'],
                mode='lines+markers',
                name=ep
            ))

            fig.update_layout(
                title=f'{ep}의 Flow Rate',
                xaxis_title='Time',
                yaxis_title='Flow Rate',
                xaxis=dict(type='date', tickformat='%H:%M:%S'),  # 2초 단위로 시간 형식 지정
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

    # 데이터 최신화 시간 표시
    st.write(f"LAST UPDATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Sidebar for statistics type selection
def statistics_page():
    st.title("STATISTICS")

    # Sidebar에서 일, 월, 연 사용량 선택
    stat_type = st.sidebar.radio("유형 선택", ["일 사용량", "월 사용량", "연 사용량"])

    # Date selection for filtering data
    if stat_type == "일 사용량":
        daily_usage_page()
    elif stat_type == "월 사용량":
        monthly_usage_page()
    elif stat_type == "연 사용량":
        yearly_usage_page()

# 일 사용량 페이지
def daily_usage_page():
    st.header("DAILY USAGE")
    
    # 날짜 선택 위젯 (기본값은 오늘)
    selected_date = st.date_input("SELECT DATE", value=datetime.now().date())
    
    # 현재 날짜를 기준으로 사용량 데이터 생성 (예시 데이터)
    num_days = (datetime.now().replace(day=1) - timedelta(days=1)).day
    daily_usage = np.random.randint(100, 300, size=num_days)
    
    # 해당 월의 날짜 생성
    days = [f"{i+1}일" for i in range(num_days)]
    
    # 막대 그래프 생성
    fig = go.Figure([go.Bar(x=days, y=daily_usage)])
    fig.update_layout(title="일별 사용량(L)")
    st.plotly_chart(fig, use_container_width=True)
    
    # 일 평균 사용량 및 요금 계산 (가정: 요금 500원/L)
    avg_usage = np.mean(daily_usage)
    avg_bill = avg_usage * 500
    
    st.subheader(f"DAILY AVERAGE USAGE: {avg_usage:.2f} L")
    st.subheader(f"DAILY AVERAGE FEE: {avg_bill:.2f} WON")

def monthly_usage_page():
    st.header("MONTHLY USAGE")

    # 연도 선택 (기본값: 현재 연도)
    current_year = datetime.now().year
    selected_year = st.selectbox("연도 선택", [current_year - i for i in range(10)], index=0)

    # 월 선택 (1월 ~ 12월)
    selected_month = st.selectbox("월 선택", [f"{i}월" for i in range(1, 13)], index=datetime.now().month - 1)

    # 예시 데이터: 선택된 연도와 월에 대한 데이터 생성
    monthly_usage = np.random.randint(3000, 10000, size=12)
    months = [f"{i+1}월" for i in range(12)]

    # 그래프 생성
    fig = go.Figure([go.Bar(x=months, y=monthly_usage)])
    fig.update_layout(title=f"{selected_year}년 {selected_month} 사용량(L)")
    st.plotly_chart(fig, use_container_width=True)

    # 월 평균 사용량 및 요금 계산
    avg_usage = np.mean(monthly_usage)
    avg_bill = avg_usage * 500
    st.subheader(f"MONTHLY AVERAGE USAGE: {avg_usage:.2f} L")
    st.subheader(f"MONTHLY AVERAGE FEE: {avg_bill:.2f} WON")


# 연 사용량 페이지 (연도만 선택할 수 있게 구현)
def yearly_usage_page():
    st.header("ANNUAL USAGE")

    # 연도 선택 (기본값: 현재 연도)
    current_year = datetime.now().year
    selected_year = st.selectbox("연도 선택", [current_year - i for i in range(10)], index=0)

    # 최근 5년간의 사용량 (예시 데이터)
    years = [(selected_year - i) for i in range(5)]
    yearly_usage = np.random.randint(30000, 100000, size=5)

    # 그래프 생성
    fig = go.Figure([go.Bar(x=years, y=yearly_usage)])
    fig.update_layout(title=f"{selected_year} 사용량(L)")
    st.plotly_chart(fig, use_container_width=True)

    # 연 평균 사용량 및 요금 계산
    avg_usage = np.mean(yearly_usage)
    avg_bill = avg_usage * 500
    st.subheader(f"ANNUAL AVERAGE USAGE: {avg_usage:.2f} L")
    st.subheader(f"ANNUAL AVERAGE FEE: {avg_bill:.2f} WON")

# 요금 데이터 초기 설정
water_fees = {
    "서울": {
        "가정용": {
            "상수도 요금": 580,
            "하수도 요금": [(30, 400), (50, 930), (float('inf'), 1420)],
            "물이용부담금": 170
        },
        "일반용": {
            "상수도 요금": 1270,
            "하수도 요금": [(30, 500), (50, 1000), (100, 1520), (200, 1830), (1000, 1920), (float('inf'), 2030)],
            "물이용부담금": 170
        }
    },
    "부산": {
        "가정용": {
            "상수도 요금": 790,
            "하수도 요금": [(10, 490), (20, 630), (30, 570), (float('inf'), 940)],
            "물이용부담금": 151.3
        },
        "일반용": {
            "상수도 요금": 1350,
            "하수도 요금": [(50, 1160), (100, 1720), (300, 2020), (float('inf'), 2110)],
            "물이용부담금": 151.3
        }
    }
}

# 하수도 요금을 계산하는 함수
def calculate_sewage_fee(usage, sewage_fees):
    fee = 0
    remaining_usage = usage
    for limit, rate in sewage_fees:
        if remaining_usage > limit:
            fee += limit * rate
            remaining_usage -= limit
        else:
            fee += remaining_usage * rate
            break
    return fee

# 수도요금 설정 페이지
def water_fee_settings_page():
    st.title("수도 요금 설정")

    # 지역 선택
    region = st.selectbox("지역 선택", ["서울", "부산"], key="region")

    # 용도 선택
    usage_type = st.selectbox("용도 선택", ["가정용", "일반용"], key="usage_type")

    # 선택한 지역과 용도에 따라 요금 정보를 가져옴
    selected_fees = water_fees[region][usage_type]

    # 요금 데이터 표시 및 수정 가능하게 구현
    st.subheader("상수도 요금 설정")
    water_fee = st.number_input("상수도 요금 (1㎥당)", value=selected_fees["상수도 요금"], key="water_fee")

    # 하수도 요금 범위를 구분하여 수정 가능하게 처리
    st.subheader("하수도 요금 설정 (㎥당)")
    sewage_fees = selected_fees["하수도 요금"]
    sewage_fee_limits = [limit for limit, rate in sewage_fees]
    sewage_fee_rates = [rate for limit, rate in sewage_fees]

    # 각 구간별 하수도 요금 수정
    for i, (limit, rate) in enumerate(sewage_fees):
        if limit != float('inf'):
            new_limit = st.number_input(f"구간 {i+1} 최대 사용량 (㎥)", value=limit, min_value=0, key=f"sewage_limit_{i}")
            new_rate = st.number_input(f"구간 {i+1} 하수도 요금 (원)", value=rate, min_value=0, key=f"sewage_rate_{i}")
            sewage_fee_limits[i] = new_limit
            sewage_fee_rates[i] = new_rate
        else:
            # 무한대 구간 처리
            new_rate = st.number_input(f"구간 {i+1} 하수도 요금 (최대 이상, 원)", value=rate, min_value=0, key=f"sewage_rate_inf")
            sewage_fee_rates[i] = new_rate

    # 물 이용부담금 수정
    st.subheader("물이용부담금 설정")
    water_use_fee = st.number_input("물이용부담금 (1㎥당)", value=selected_fees["물이용부담금"], key="water_use_fee")

    # 수정된 값으로 요금 데이터 업데이트
    if st.button("수정된 요금 저장"):
        water_fees[region][usage_type]["상수도 요금"] = water_fee
        water_fees[region][usage_type]["하수도 요금"] = [(limit, rate) for limit, rate in zip(sewage_fee_limits, sewage_fee_rates)]
        water_fees[region][usage_type]["물이용부담금"] = water_use_fee
        st.success(f"{region} {usage_type} 요금이 수정되었습니다.")

# 요금 시뮬레이션 페이지
def fee_simulation_page():
    st.title("요금 시뮬레이션")

    # 지역 선택
    region = st.selectbox("지역 선택", ["서울", "부산"], key="sim_region")

    # 용도 선택
    usage_type = st.selectbox("용도 선택", ["가정용", "일반용"], key="sim_usage_type")

    # 선택한 지역과 용도에 따른 요금 데이터 불러오기
    selected_fees = water_fees[region][usage_type]

    # 물 사용량 입력
    water_usage = st.number_input("물 사용량 입력 (㎥)", min_value=0.0, step=0.1, key="water_usage")

    if water_usage:
        # 요금 계산
        water_fee = water_usage * selected_fees["상수도 요금"]
        sewage_fee = calculate_sewage_fee(water_usage, selected_fees["하수도 요금"])
        water_use_fee = water_usage * selected_fees["물이용부담금"]
        total_fee = water_fee + sewage_fee + water_use_fee

        # 계산된 요금 표시
        st.write(f"상수도 요금: {water_fee:.2f} 원")
        st.write(f"하수도 요금: {sewage_fee:.2f} 원")
        st.write(f"물이용부담금: {water_use_fee:.2f} 원")
        st.subheader(f"총 요금: {total_fee:.2f} 원")

# Firestore에서 그룹 정보를 가져오는 함수
def load_groups_from_firestore():
    doc_ref = db.collection('Waterflow_data').document('groups')  # 적절한 문서 경로 설정
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return {}

# Firestore에 그룹 정보를 저장하는 함수
def save_groups_to_firestore(groups):
    doc_ref = db.collection('Waterflow_data').document('groups')
    doc_ref.set(groups)

# 그룹을 생성하고 저장하는 함수 (구역 설정)
def region_settings_page():
    st.title("그룹 설정")

    # 세션 상태에서 그룹 불러오기
    if 'groups' not in st.session_state:
        st.session_state.groups = load_groups_from_firestore()  # Firestore에서 그룹 불러오기

    st.subheader("디바이스 사용자 정의")
    group_name = st.text_input("그룹 이름을 입력하세요")
    
    # EP 목록을 선택하여 그룹으로 설정
    selected_eps = st.multiselect("그룹에 포함할 디바이스 선택", EP_LIST)

    if st.button("그룹 저장"):
        if group_name and selected_eps:
            # 그룹을 저장
            st.session_state.groups[group_name] = selected_eps
            save_groups_to_firestore(st.session_state.groups)  # Firestore에 그룹 저장
            st.success(f"그룹 '{group_name}'이(가) 성공적으로 저장되었습니다.")
        else:
            st.error("그룹 이름과 디바이스 선택은 필수입니다.")

    # 저장된 그룹 보여주기
    st.subheader("저장된 그룹")
    
    # 삭제할 그룹을 저장할 리스트
    groups_to_delete = []

    if st.session_state.groups:
        for group_name, eps in st.session_state.groups.items():
            col1, col2 = st.columns([3, 1])  # 두 개의 열 생성
            with col1:
                st.write(f"**{group_name}**: {', '.join(eps)}")
            with col2:
                # 그룹 삭제 버튼
                if st.button("삭제", key=group_name):  # 고유 키를 사용하여 각 버튼 구분
                    groups_to_delete.append(group_name)  # 삭제할 그룹을 리스트에 추가

        # 삭제할 그룹이 있으면 세션 상태에서 삭제
        for group in groups_to_delete:
            del st.session_state.groups[group]  # 세션 상태에서 그룹 삭제
            save_groups_to_firestore(st.session_state.groups)  # Firestore에 업데이트
            st.success(f"그룹 '{group}'이(가) 삭제되었습니다.")
    else:
        st.write("아직 저장된 그룹이 없습니다.")


# 그룹의 EP 데이터를 합산하는 함수
def calculate_group_data(group_eps, ep_data):
    # 그룹 내 모든 EP의 데이터를 합산
    total_data = pd.DataFrame(columns=['timestamp', 'flowRate'])
    for ep in group_eps:
        ep_data[ep]['timestamp'] = pd.to_datetime(ep_data[ep]['timestamp'])
        total_data = pd.concat([total_data, ep_data[ep]])

    # 타임스탬프별로 데이터 합산
    total_data = total_data.groupby('timestamp').sum().reset_index()

    return total_data

# 설정 페이지 구현
def settings_page():
    st.title("SETTINGS")

    # 사이드바에서 설정 메뉴 선택
    settings_menu = st.sidebar.radio("설정 메뉴", ["그룹 설정", "수도 요금 설정", "요금 시뮬레이션"])

    if settings_menu == "그룹 설정":
        region_settings_page()
    elif settings_menu == "수도 요금 설정":
        water_fee_settings_page()  # 기존 구현된 수도 요금 설정 함수
    elif settings_menu == "요금 시뮬레이션":
        fee_simulation_page()  # 기존 구현된 요금 시뮬레이션 함수

# 페이지 전환을 위한 함수 정의 (콜백 함수로 사용)
def set_page(page_name):
    st.session_state.page = page_name

# 사이드바 메뉴
with st.sidebar:
    st.markdown("""
        <style>
        [data-testid="collapsedControl"] {
            display: none;
        }
        [data-testid="stSidebar"] {
            min-width: 200px;
            max-width: 200px;  /* 사이드바 너비 조정 */
        }
        .stButton button {
            width: 100%;  /* 버튼 너비 고정 */
            height: 50px; /* 버튼 높이 고정 */
            font-size: 18px; /* 버튼 텍스트 크기 */
        }
        </style>
    """, unsafe_allow_html=True)

    st.button('홈', on_click=set_page, args=('home',))
    st.button('실시간', on_click=set_page, args=('realtime',))
    st.button('통계', on_click=set_page, args=('statistics',))
    st.button('설정', on_click=set_page, args=('settings',))

# 메인 페이지 구성
def main():
    # 현재 페이지에 따라 다른 페이지를 표시
    if 'page' not in st.session_state:
        st.session_state.page = 'home'
    
    if st.session_state.page == 'home':
        home_page()
    elif st.session_state.page == 'realtime':
        realtime_data_page()
    elif st.session_state.page == 'statistics':
        statistics_page()
    elif st.session_state.page == 'settings':
        settings_page()

if __name__ == "__main__":
    main()