import streamlit as st
import pandas as pd
import mysql.connector
import time

# ---------------------------------------------------------
# 1. MySQL 연결 설정 (코드에 직접 입력)
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="마당서점 (MySQL 연동)")

# [수정] 사이드바 입력창을 없애고, 여기에 직접 값을 넣으세요.
HOST = "192.168.80.130"  # 우분투 IP 주소
USER = "root"            # MySQL 사용자 아이디
PASSWORD = "1234"        # MySQL 비밀번호 (여기에 입력)
DATABASE = "madang"      # 데이터베이스 이름

st.title("마당서점 고객 관리")

# DB 연결 함수
def get_connection():
    return mysql.connector.connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        database=DATABASE
    )

# ---------------------------------------------------------
# 2. 세션 상태 초기화
# ---------------------------------------------------------
if 'custid' not in st.session_state:
    st.session_state.custid = None
if 'name' not in st.session_state:
    st.session_state.name = None

# 탭 구분
tab1, tab2 = st.tabs(["고객 관리", "거래 입력"])

try:
    # DB 연결 시도
    conn = get_connection()
    cursor = conn.cursor()
except Exception as e:
    st.error(f"DB 연결 실패! 코드 상단의 IP와 비밀번호를 확인해주세요.\n에러 메시지: {e}")
    st.stop() # 연결 실패 시 실행 중단

# ---------------------------------------------------------
# [Tab 1] 고객 조회 및 신규 등록
# ---------------------------------------------------------
with tab1:
    search_name = st.text_input("고객명 입력", key="search_input")
    
    if st.button("조회") or search_name:
        st.session_state.name = search_name
        
        # [MySQL] pandas.read_sql을 사용하여 DataFrame으로 가져옵니다.
        sql_check = f"SELECT * FROM Customer WHERE name = '{search_name}'"
        df_customer = pd.read_sql(sql_check, conn)

        # 분기 처리
        if df_customer.empty:
            # [Case A] 없는 사람 -> 신규 등록
            st.session_state.custid = None
            
            st.warning(f"'{search_name}' 고객님은 등록되지 않았습니다.")
            st.info("신규 고객으로 등록하시겠습니까?")
            
            with st.form("register_form"):
                new_addr = st.text_input("주소")
                new_phone = st.text_input("전화번호")
                
                if st.form_submit_button("신규 등록"):
                    # custid 자동 생성 (MySQL)
                    cursor.execute("SELECT MAX(custid) FROM Customer")
                    max_val = cursor.fetchone() # 결과가 (값,) 튜플 형태
                    
                    if max_val[0] is None:
                        new_id = 1
                    else:
                        new_id = max_val[0] + 1

                    # INSERT 실행
                    insert_sql = "INSERT INTO Customer(custid, name, address, phone) VALUES (%s, %s, %s, %s)"
                    val = (new_id, search_name, new_addr, new_phone)
                    
                    try:
                        cursor.execute(insert_sql, val)
                        conn.commit() # MySQL은 commit 필수!
                        
                        st.success(f"{search_name} 고객 등록 완료! (ID: {new_id})")
                        st.session_state.custid = new_id
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"등록 실패: {e}")

        else:
            # [Case B] 있는 사람
            st.success(f"'{search_name}' 고객님을 찾았습니다.")
            
            current_custid = df_customer['custid'].iloc[0]
            st.session_state.custid = current_custid
            
            # 거래 내역 조회
            history_sql = f"""
                SELECT c.name, b.bookname, o.orderdate, o.saleprice
                FROM Customer c
                JOIN Orders o ON c.custid = o.custid
                JOIN Book b ON o.bookid = b.bookid
                WHERE c.name = '{search_name}'
            """
            history_df = pd.read_sql(history_sql, conn)
            
            if history_df.empty:
                st.write("거래 내역이 없습니다.")
            else:
                st.write("거래 내역:", history_df)

# ---------------------------------------------------------
# [Tab 2] 거래 입력
# ---------------------------------------------------------
with tab2:
    current_custid = st.session_state.get('custid')
    current_name = st.session_state.get('name')

    if current_custid is None:
        st.warning("먼저 '고객 관리' 탭에서 고객을 검색하거나 등록해주세요.")
    else:
        st.info(f"고객명: {current_name} (고객번호: {current_custid})")
        
        # 책 목록 가져오기
        books_df = pd.read_sql("SELECT bookid, bookname FROM Book", conn)
        
        if books_df.empty:
            st.error("등록된 책이 없습니다.")
        else:
            book_options = [f"{row['bookid']},{row['bookname']}" for idx, row in books_df.iterrows()]
            
            select_book = st.selectbox("구매 서적:", book_options)
            price = st.text_input("판매 금액")
            
            if st.button("거래 입력"):
                if not price:
                    st.error("판매 금액을 입력하세요.")
                else:
                    bookid = select_book.split(",")[0]
                    dt = time.strftime('%Y-%m-%d', time.localtime())
                    
                    # orderid 생성
                    cursor.execute("SELECT MAX(orderid) FROM Orders")
                    res = cursor.fetchone()
                    
                    if res[0] is None:
                        orderid = 1
                    else:
                        orderid = res[0] + 1
                    
                    # INSERT 실행
                    order_sql = "INSERT INTO Orders(orderid, custid, bookid, saleprice, orderdate) VALUES (%s, %s, %s, %s, %s)"
                    val = (orderid, current_custid, bookid, price, dt)
                    
                    try:
                        cursor.execute(order_sql, val)
                        conn.commit()
                        st.success("거래가 입력되었습니다.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

# 연결 종료 (스크립트 끝)
if conn.is_connected():
    cursor.close()
    conn.close()