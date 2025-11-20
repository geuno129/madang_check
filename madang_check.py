import streamlit as st
import pandas as pd
import duckdb
import time
import os

# ---------------------------------------------------------
# 1. 페이지 및 DB 설정
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="마당서점 (DuckDB 연동)")
st.title("마당서점 고객 관리")

# 데이터베이스 파일 경로
DB_PATH = "madang.db"

# 초기 CSV 파일 경로 (DB 초기화용)
FILE_CUSTOMER = "Customer_madang.csv"
FILE_BOOK = "Book_madang.csv"
FILE_ORDERS = "Orders_madang.csv"

# ---------------------------------------------------------
# 2. 데이터베이스 연결 및 초기화 함수
# ---------------------------------------------------------
def get_connection():
    """DuckDB 연결 객체를 반환합니다."""
    return duckdb.connect(DB_PATH)

def init_db():
    """테이블이 없으면 생성하고, CSV 파일이 있다면 데이터를 import 합니다."""
    conn = get_connection()
    
    # 1. Customer 테이블 생성
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Customer (
            custid INTEGER PRIMARY KEY,
            name VARCHAR,
            address VARCHAR,
            phone VARCHAR
        )
    """)
    
    # 2. Book 테이블 생성
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Book (
            bookid INTEGER PRIMARY KEY,
            bookname VARCHAR,
            publisher VARCHAR,
            price INTEGER
        )
    """)
    
    # 3. Orders 테이블 생성
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Orders (
            orderid INTEGER PRIMARY KEY,
            custid INTEGER,
            bookid INTEGER,
            saleprice INTEGER,
            orderdate VARCHAR
        )
    """)
    
    # --- 초기 데이터 마이그레이션 (테이블이 비어있고 CSV가 있을 때) ---
    
    # Customer
    if conn.execute("SELECT count(*) FROM Customer").fetchone()[0] == 0:
        if os.path.exists(FILE_CUSTOMER):
            conn.execute(f"INSERT INTO Customer SELECT * FROM read_csv_auto('{FILE_CUSTOMER}')")
            st.toast("Customer 데이터 가져오기 완료")

    # Book
    if conn.execute("SELECT count(*) FROM Book").fetchone()[0] == 0:
        if os.path.exists(FILE_BOOK):
            conn.execute(f"INSERT INTO Book SELECT * FROM read_csv_auto('{FILE_BOOK}')")
            st.toast("Book 데이터 가져오기 완료")

    # Orders
    if conn.execute("SELECT count(*) FROM Orders").fetchone()[0] == 0:
        if os.path.exists(FILE_ORDERS):
            conn.execute(f"INSERT INTO Orders SELECT * FROM read_csv_auto('{FILE_ORDERS}')")
            st.toast("Orders 데이터 가져오기 완료")
            
    return conn

# 앱 시작 시 DB 연결 및 초기화
try:
    conn = init_db()
except Exception as e:
    st.error(f"DB 초기화 중 오류 발생: {e}")
    st.stop()

# ---------------------------------------------------------
# 3. 세션 상태 초기화
# ---------------------------------------------------------
if 'custid' not in st.session_state:
    st.session_state.custid = None
if 'name' not in st.session_state:
    st.session_state.name = None

# 탭 구분
tab1, tab2 = st.tabs(["고객 관리", "거래 입력"])

# ---------------------------------------------------------
# [Tab 1] 고객 조회 및 신규 등록
# ---------------------------------------------------------
with tab1:
    st.header("고객 조회")
    search_name = st.text_input("고객명 입력", key="search_input")
    
    if st.button("조회") or search_name:
        st.session_state.name = search_name
        
        # [DuckDB] SQL SELECT 실행
        # name이 일치하는 고객 찾기
        query = "SELECT * FROM Customer WHERE name = ?"
        # duckdb execute 결과에서 .df()를 호출하면 Pandas DataFrame으로 변환됨
        df_customer = conn.execute(query, [search_name]).df()

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
                    # custid 자동 생성 (MAX + 1)
                    max_id = conn.execute("SELECT MAX(custid) FROM Customer").fetchone()[0]
                    new_id = 1 if max_id is None else max_id + 1

                    # [DuckDB] SQL INSERT 실행
                    insert_sql = "INSERT INTO Customer VALUES (?, ?, ?, ?)"
                    conn.execute(insert_sql, [new_id, search_name, new_addr, new_phone])
                    
                    st.success(f"{search_name} 고객 등록 완료! (ID: {new_id})")
                    st.session_state.custid = new_id
                    time.sleep(1)
                    st.rerun()

        else:
            # [Case B] 있는 사람
            st.success(f"'{search_name}' 고객님을 찾았습니다.")
            
            # 첫 번째 결과 가져오기
            current_custid = int(df_customer.iloc[0]['custid'])
            st.session_state.custid = current_custid
            
            st.subheader("구매 내역")
            
            # [DuckDB] SQL JOIN 쿼리 사용
            history_sql = """
                SELECT c.name, b.bookname, o.orderdate, o.saleprice
                FROM Orders o
                JOIN Customer c ON o.custid = c.custid
                JOIN Book b ON o.bookid = b.bookid
                WHERE c.custid = ?
                ORDER BY o.orderdate DESC
            """
            df_history = conn.execute(history_sql, [current_custid]).df()
            
            if df_history.empty:
                st.write("거래 내역이 없습니다.")
            else:
                st.dataframe(df_history)

# ---------------------------------------------------------
# [Tab 2] 거래 입력
# ---------------------------------------------------------
with tab2:
    st.header("신규 거래 입력")
    
    current_custid = st.session_state.get('custid')
    current_name = st.session_state.get('name')

    if current_custid is None:
        st.warning("먼저 '고객 관리' 탭에서 고객을 검색하거나 등록해주세요.")
    else:
        st.info(f"선택된 고객: {current_name} (고객번호: {current_custid})")
        
        # 책 목록 가져오기
        df_book = conn.execute("SELECT bookid, bookname FROM Book").df()
        
        if df_book.empty:
            st.error("등록된 책이 없습니다.")
        else:
            # Selectbox 옵션 생성
            book_options = [f"{row['bookid']},{row['bookname']}" for idx, row in df_book.iterrows()]
            
            select_book = st.selectbox("구매 서적 선택:", book_options)
            price = st.text_input("판매 금액 (숫자만 입력)")
            
            if st.button("거래 입력"):
                if not price:
                    st.error("판매 금액을 입력하세요.")
                else:
                    try:
                        # 데이터 준비
                        bookid = int(select_book.split(",")[0])
                        saleprice = int(price)
                        orderdate = time.strftime('%Y-%m-%d', time.localtime())
                        
                        # orderid 생성 (MAX + 1)
                        max_order_id = conn.execute("SELECT MAX(orderid) FROM Orders").fetchone()[0]
                        new_order_id = 1 if max_order_id is None else max_order_id + 1
                        
                        # [DuckDB] SQL INSERT 실행
                        insert_sql = """
                            INSERT INTO Orders (orderid, custid, bookid, saleprice, orderdate)
                            VALUES (?, ?, ?, ?, ?)
                        """
                        conn.execute(insert_sql, [new_order_id, current_custid, bookid, saleprice, orderdate])
                        
                        st.success("거래가 정상적으로 입력되었습니다.")
                        time.sleep(1)
                        st.rerun()
                        
                    except ValueError:
                        st.error("금액은 숫자로 입력해주세요.")
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

# 스크립트 종료 전 연결은 DuckDB가 알아서 처리하지만, 명시적으로 닫아주려면 아래와 같이 할 수 있습니다.
# 하지만 Streamlit 특성상 매 실행마다 연결 객체가 새로 생성되므로, 전역 conn 객체를 유지하는 것이 일반적입니다.


