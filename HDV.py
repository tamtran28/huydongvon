import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# --------------------------
# Hàm xuất Excel
# --------------------------
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False)
    writer.close()
    return output.getvalue()

# ===============================
# Giao diện chính
# ===============================
st.title("📊 HỆ THỐNG TC1 – TC2 – TC3 (HDV – FTP – THỰC TRẢ – XẾP HẠNG – RÚT/NỘP)")
st.markdown("Tích hợp toàn bộ các chỉ tiêu kiểm tra HDV trong 1 ứng dụng duy nhất.")

tab1, tab2, tab3 = st.tabs([
    "🔵 TC1 – HDV – FTP – Thực trả",
    "🟡 TC2 – Xếp hạng khách hàng",
    "🟣 TC3 – Gửi rút trong 7 ngày"
])

# ==========================================================
# TAB 1 – TC1
# ==========================================================
with tab1:
    st.header("🔵 TC1: Ghép HDV – FTP – Lãi suất thực trả")

    hdv_files = st.file_uploader("📂 Upload file HDV (CKH)", accept_multiple_files=True)
    ftp_files = st.file_uploader("📂 Upload file FTP", accept_multiple_files=True)
    tt_file  = st.file_uploader("📂 Upload file Lãi suất thực trả", accept_multiple_files=False)

    chi_nhanh = st.text_input("Nhập chi nhánh / SOL (VD: HANOI hoặc 001):").strip().upper()
    run_tc1 = st.button("🚀 Chạy TC1")

    if run_tc1:

        if not hdv_files or not ftp_files or not tt_file:
            st.error("⚠ Vui lòng upload đầy đủ file HDV – FTP – TT!")
            st.stop()

        cols_ckh = [
            'BRCD','DEPTCD','CUST_TYPE','NMLOC','CUSTSEQ','BIRTH_DAY','IDXACNO','SCHM_NAME','TERM_DAYS',
            'GL_SUB','CCYCD','CURBAL_NT','CURBAL_VN','OPNDT_FIRST','OPNDT_EFFECT','MATDT',
            'LS_GHISO','LS_CONG_BO','PROMO_CD','KH_VIP','CIF_OPNDT','DP_MTHS','DP_DAYS',
            'PROMO_NM','PHANKHUC_KH'
        ]
        df_ckh = pd.concat([pd.read_excel(f, usecols=cols_ckh, dtype=str) for f in hdv_files])

        cols_ftp = ['CUSTSEQ','NMLOC','IDXACNO','KY_HAN','LS_FTP']
        df_ftp = pd.concat([pd.read_excel(f, usecols=cols_ftp, dtype=str) for f in ftp_files])

        df_tt = pd.read_excel(tt_file, usecols=['Số tài khoản','Lãi suất thực trả'])
        df_tt.columns = ['IDXACNO','LS_THUC_TRA']
        df_tt['IDXACNO'] = df_tt['IDXACNO'].astype(str)

        df_filtered = df_ckh[df_ckh['BRCD'].str.upper().str.contains(chi_nhanh)]

        df_ftp_small = df_ftp[['IDXACNO', 'LS_FTP']].drop_duplicates()
        df_merge = df_filtered.merge(df_ftp_small, on='IDXACNO', how='left')
        df_merge = df_merge.merge(df_tt, on='IDXACNO', how='left')

        df_merge['LSGS ≠ LSCB'] = (df_merge['LS_GHISO'] != df_merge['LS_CONG_BO']).map({True:'X', False:''})
        df_merge['Không có LS trình duyệt'] = df_merge['LS_THUC_TRA'].isna().map({True:'X', False:''})
        df_merge['LSGS > FTP'] = (
            (df_merge['LS_FTP'].notna()) &
            (df_merge['LS_GHISO'].notna()) &
            (df_merge['LS_GHISO'].astype(float) > df_merge['LS_FTP'].astype(float))
        ).map({True:'X', False:''})

        st.success("🎉 TC1 hoàn thành!")
        st.dataframe(df_merge.head(20))

        st.download_button("⬇ Tải TC1.xlsx",
                           data=to_excel(df_merge),
                           file_name="TC1.xlsx")

# ==========================================================
# TAB 2 – TC2
# ==========================================================
with tab2:
    st.header("🟡 TC2: Xếp hạng KH – Tổng hợp số dư – Đánh dấu VIP & tuổi")

    ckh_files = st.file_uploader("📂 Upload file CKH", accept_multiple_files=True)
    kkh_files = st.file_uploader("📂 Upload file KKH", accept_multiple_files=True)

    chi_nhanh2 = st.text_input("Nhập chi nhánh / SOL cho TC2:").strip().upper()

    run_tc2 = st.button("🚀 Chạy TC2")

    if run_tc2:
        if not ckh_files or not kkh_files:
            st.error("⚠ Cần upload file CKH và KKH!")
            st.stop()

        cols_needed = [
            'BRCD','DEPTCD','CUST_TYPE','CUSTSEQ','NMLOC','BIRTH_DAY','IDXACNO',
            'SCHM_NAME','TERM_DAYS','GL_SUB','CCYCD','CURBAL_NT','CURBAL_VN',
            'OPNDT_FIRST','OPNDT_EFFECT','MATDT','LS_GHISO','LS_CONG_BO',
            'PROMO_CD','KH_VIP','CIF_OPNDT'
        ]

        df_ckh = pd.concat([pd.read_excel(f, dtype=str)[cols_needed] for f in ckh_files])
        df_kkh = pd.concat([pd.read_excel(f, dtype=str)[cols_needed] for f in kkh_files])

        df_ckh_filtered = df_ckh[df_ckh['BRCD'].str.upper().str.contains(chi_nhanh2)]
        df_kkh_filtered = df_kkh[df_kkh['BRCD'].str.upper().str.contains(chi_nhanh2)]

        df = pd.concat([df_ckh_filtered, df_kkh_filtered])

        df['CURBAL_VN'] = pd.to_numeric(df['CURBAL_VN'], errors='coerce')

        df_sum = df.groupby('CUSTSEQ', as_index=False)['CURBAL_VN'].sum()
        df_sum.columns = ['CUSTSEQ','SỐ DƯ']

        df = df.drop_duplicates(subset='CUSTSEQ').merge(df_sum, on='CUSTSEQ', how='left')

        df['BIRTH_DAY'] = pd.to_datetime(df['BIRTH_DAY'], errors='coerce', dayfirst=True)

        today = pd.Timestamp.today().normalize()

        mask = df['CUST_TYPE'] == 'KHCN'
        df.loc[mask, 'ĐỘ TUỔI'] = df.loc[mask, 'BIRTH_DAY'].apply(
            lambda x: today.year - x.year if pd.notnull(x) else None
        )

        df['RANK_RAW'] = df.groupby('CUST_TYPE')['SỐ DƯ'].rank(method='min', ascending=False)

        df['TOP10_KHDN'] = df.apply(lambda x: 'X' if x['CUST_TYPE']=='KHDN' and x['RANK_RAW']<=10 else '', axis=1)
        df['TOP10_KHCN'] = df.apply(lambda x: 'X' if x['CUST_TYPE']=='KHCN' and x['RANK_RAW']<=10 else '', axis=1)

        df['VIP_KHDN'] = df.apply(lambda x: 'X' if x['CUST_TYPE']=='KHDN' and x['KH_VIP']!='General' else '', axis=1)
        df['VIP_KHCN'] = df.apply(lambda x: 'X' if x['CUST_TYPE']=='KHCN' and x['KH_VIP']!='General' else '', axis=1)

        df['>70_TUOI'] = df.apply(lambda x: 'X' if x['CUST_TYPE']=='KHCN' and x['ĐỘ TUỔI']>=70 else '', axis=1)

        df_final = df.sort_values(by=['CUST_TYPE','SỐ DƯ'], ascending=[True,False])

        st.success("🎉 TC2 hoàn thành!")
        st.dataframe(df_final.head(20))

        st.download_button("⬇ Tải TC2.xlsx",
                           data=to_excel(df_final),
                           file_name="TC2.xlsx")

# ==========================================================
# TAB 3 – TC3
# ==========================================================
with tab3:

    st.header("🟣 TC3: Gửi rút trong 7 ngày – giao dịch lớn – camera 90 ngày")

    tc3_file = st.file_uploader("📂 Upload file TC3", accept_multiple_files=False)
    sol3 = st.text_input("Nhập SOL_ID TC3:").strip().upper()
    run_tc3 = st.button("🚀 Chạy TC3")

    if run_tc3:

        if not tc3_file:
            st.error("⚠ Cần upload file TC3!")
            st.stop()

        df = pd.read_excel(tc3_file, dtype=str)

        df = df[df['SOL_ID'].str.upper().str.contains(sol3)]

        df['NGAY_HACH_TOAN'] = pd.to_datetime(df['NGAY_HACH_TOAN'], errors='coerce')
        df['ACCT_OPN_DATE'] = pd.to_datetime(df['ACCT_OPN_DATE'], errors='coerce')
        df['PART_CLOSE_AMT'] = pd.to_numeric(df['PART_CLOSE_AMT'], errors='coerce')

        df['CHENH_LECH_NGAY'] = (df['NGAY_HACH_TOAN'] - df['ACCT_OPN_DATE']).dt.days

        df['MO_RUT_CUNG_NGAY'] = df['CHENH_LECH_NGAY'].apply(lambda x: 'X' if x == 0 else '')
        df['MO_RUT_1_3_NGAY'] = df['CHENH_LECH_NGAY'].apply(lambda x: 'X' if 0 < x <= 3 else '')
        df['MO_RUT_4_7_NGAY'] = df['CHENH_LECH_NGAY'].apply(lambda x: 'X' if 4 <= x <= 7 else '')

        df['GD_LON_HON_1TY'] = df['PART_CLOSE_AMT'].apply(lambda x: 'X' if x > 1_000_000_000 else '')

        today = pd.to_datetime(datetime.today().date())
        df['TRONG_THOI_HIEU_CAMERA'] = df['NGAY_HACH_TOAN'].apply(
            lambda x: 'X' if pd.notnull(x) and (today - x).days <= 90 else ''
        )

        st.success("🎉 TC3 hoàn thành!")
        st.dataframe(df.head(20))

        st.download_button("⬇ Tải TC3.xlsx",
                           data=to_excel(df),
                           file_name="TC3.xlsx")
