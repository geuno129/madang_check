import pandas as pd
import streamlit as st
import time
import pymysql
import time

dbConn = pymysql.connect(user='root', passwd='1234', host='192.168.80.130', db='madang', charset='utf8')
cursor = dbConn.cursor(pymysql.cursors.DictCursor)
# ... (DB 연결 부분 생략) ...

st.title("마당서점 고객 관리")

# 탭 구분
tab1, tab2 = st.tabs(["고객 관리", "거래 입력"])

# ---------------------------------------------------------
# [Tab 1] 고객 조회 및 신규 등록
# ---------------------------------------------------------
with tab1:
    name = st.text_input("고객명 입력", key="search_name")
    
    # 전역 변수처럼 쓰기 위해 custid 초기화
    current_custid = None 

    if name:
        # 1단계: 일단 고객 테이블(Customer)에 이 사람이 있는지 확인! (Orders랑 조인 X)
        sql_check = f"SELECT * FROM Customer WHERE name = '{name}'"
        cursor.execute(sql_check)
        customer_data = cursor.fetchall()
        df_customer = pd.DataFrame(customer_data)

        # 2단계: 분기 처리
        if df_customer.empty:
            # ------------------------------------------------
            # [Case A] 없는 사람 -> 신규 등록 기능 노출
            # ------------------------------------------------
            st.warning(f"'{name}' 고객님은 등록되지 않았습니다.")
            st.info("신규 고객으로 등록하시겠습니까?")
            
            with st.form("register_form"):
                new_addr = st.text_input("주소")
                new_phone = st.text_input("전화번호")
                
                if st.form_submit_button("신규 등록"):
                    # custid 자동 생성 (Max + 1)
                    cursor.execute("SELECT MAX(custid) FROM Customer")
                    max_val = cursor.fetchone()
                    # 가져온 값이 딕셔너리인지 튜플인지 확인하여 처리
                    try:
                        new_id = list(max_val.values())[0] + 1
                    except:
                        new_id = 1 # 데이터가 없을 경우 1번부터 시작

                    # Customer 테이블에 INSERT (이게 핵심!)
                    insert_sql = f"INSERT INTO Customer(custid, name, address, phone) VALUES ({new_id}, '{name}', '{new_addr}', '{new_phone}')"
                    
                    try:
                        cursor.execute(insert_sql)
                        dbConn.commit() # 커밋 필수
                        st.success(f"{name} 고객 등록 완료! (ID: {new_id})")
                        current_custid = new_id # 등록된 ID 저장
                    except Exception as e:
                        st.error(f"등록 실패: {e}")

        else:
            # ------------------------------------------------
            # [Case B] 있는 사람 -> 거래 내역 보여주기 (슬라이드 1번 내용)
            # ------------------------------------------------
            st.success(f"'{name}' 고객님을 찾았습니다.")
            current_custid = df_customer['custid'][0] # ID 확보
            
            # 거래 내역 조회 (Inner Join)
            history_sql = f"""
                SELECT c.name, b.bookname, o.orderdate, o.saleprice 
                FROM Customer c, Book b, Orders o 
                WHERE c.custid = o.custid AND o.bookid = b.bookid AND c.name = '{name}'
            """
            cursor.execute(history_sql)
            history_df = pd.DataFrame(cursor.fetchall())
            st.write("거래 내역:", history_df)

# ---------------------------------------------------------
# [Tab 2] 거래 입력 (슬라이드 2번 내용 응용)
# ---------------------------------------------------------
with tab2:
    if current_custid is None:
        st.warning("먼저 '고객 관리' 탭에서 고객을 검색하거나 등록해주세요.")
    else:
        st.write(f"고객명: {name} (고객번호: {current_custid})")
        
        # 책 목록 가져오기 (예시)
        books = ["1,축구의 역사", "2,축구아는 여자", "3,축구의 이해"] 
        select_book = st.selectbox("구매 서적:", books)
        price = st.text_input("판매 금액")
        
        if st.button("거래 입력"):
            bookid = select_book.split(",")[0]
            dt = time.strftime('%Y-%m-%d', time.localtime())
            
            # orderid 생성
            cursor.execute("SELECT MAX(orderid) FROM Orders")
            res = cursor.fetchone()
            try:
                orderid = list(res.values())[0] + 1
            except:
                orderid = 1
                
            # Orders 테이블에 INSERT
            order_sql = f"INSERT INTO Orders(orderid, custid, bookid, saleprice, orderdate) VALUES ({orderid}, {current_custid}, {bookid}, {price}, '{dt}')"
            
            cursor.execute(order_sql)
            dbConn.commit()
            st.success("거래가 입력되었습니다.")
            