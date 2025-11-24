import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime

# =============================================================
# HÀM XUẤT EXCEL
# =============================================================
def to_excel(df, sheet_name="Sheet1"):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine="xlsxwriter")
    df.to_excel(writer, index=False, sheet_name=sheet_name)
    writer.close()
    return output.getvalue()


# =============================================================
# HÀM ĐỌC FILE EXCEL KHÔNG CẦN XLRD
# → Tất cả .xls và .xlsx đều đọc bằng openpyxl
# =============================================================
def read_excel_auto(file, usecols=None, dtype=str):
    try:
        return pd.read_excel(file, usecols=usecols, dtype=dtype, engine="openpyxl")
    except Exception as e:
        st.error("❌ Không đọc được file Excel. Vui lòng mở file rồi Save As → .xlsx")
        st.error(str(e))
        st.stop()


# =============================================================
# GIAO DIỆN
# =============================================================
st.title("📊 HỆ THỐNG HDV – TC1 / TC2 / TC3 (No-XLRD Version)")
st.markdown("Phiên bản an toàn – không dùng xlrd – chạy ổn định trên Streamlit Cloud.")

tab1, tab2, tab3 = st.tabs([
    "🔵 TC1 – HDV / FTP / Thực trả",
    "🟡 TC2 – Xếp hạng KH",
    "🟣 TC3 – Gửi rút 1–7 ngày"
])

# =============================================================
# ----------------------------- TC1 ----------------------------
# =============================================================
with tab1:
    st.header("🔵 TC1 – Ghép HDV – FTP – Lãi suất thực trả")

    hdv_files = st.file_uploader("📂 Upload file HDV", accept_multiple_files=True)
    ftp_files = st.file_uploader("📂 Upload file FTP", accept_multiple_files=True)
    tt_file = st.file_uploader("📂 Upload file Lãi suất thực trả", accept_multiple_files=False)

    chi_nhanh_tc1 = st.text_input("Nhập SOL (VD: 001 hoặc HANOI):").strip().upper()

    if st.button("🚀 Chạy TC1"):

        if not hdv_files or not ftp_files or not tt_file:
            st.error("⚠ Thiếu file đầu vào!")
            st.stop()

        cols_ckh = [
            'BRCD','DEPTCD','CUST_TYPE','NMLOC','CUSTSEQ','BIRTH_DAY','IDXACNO',
            'SCHM_NAME','TERM_DAYS','GL_SUB','CCYCD','CURBAL_NT','CURBAL_VN',
            'OPNDT_FIRST','OPNDT_EFFECT','MATDT','LS_GHISO','LS_CONG_BO',
            'PROMO_CD','KH_VIP','CIF_OPNDT','DP_MTHS','DP_DAYS','PROMO_NM','PHANKHUC_KH'
        ]

        df_ckh = pd.concat(
            [read_excel_auto(f, usecols=cols_ckh) for f in hdv_files],
            ignore_index=True
        )

        cols_ftp = ['CUSTSEQ','NMLOC','IDXACNO','KY_HAN','LS_FTP']
        df_ftp = pd.concat(
            [read_excel_auto(f, usecols=cols_ftp) for f in ftp_files],
            ignore_index=True
        )

        df_tt = read_excel_auto(tt_file, usecols=['Số tài khoản','Lãi suất thực trả'])
        df_tt.columns = ['IDXACNO','LS_THUC_TRA']
        df_tt['IDXACNO'] = df_tt['IDXACNO'].astype(str)

        df_fil = df_ckh[df_ckh['BRCD'].str.upper().str.contains(chi_nhanh_tc1)]

        df_ftp2 = df_ftp[['IDXACNO','LS_FTP']].drop_duplicates()
        df_merge = df_fil.merge(df_ftp2, on="IDXACNO", how="left")
        df_merge = df_merge.merge(df_tt, on="IDXACNO", how="left")

        df_merge['LSGS ≠ LSCB'] = (df_merge['LS_GHISO'] != df_merge['LS_CONG_BO']).map({True:'X',False:''})
        df_merge['Không có LS trình duyệt'] = df_merge['LS_THUC_TRA'].isna().map({True:'X',False:''})

        def to_float(x):
            try: return float(str(x).replace(',',''))
            except: return np.nan

        df_merge['LSGS_NUM'] = df_merge['LS_GHISO'].apply(to_float)
        df_merge['FTP_NUM'] = df_merge['LS_FTP'].apply(to_float)

        df_merge['LSGS > FTP'] = (
            df_merge['LSGS_NUM'].notna() &
            df_merge['FTP_NUM'].notna() &
            (df_merge['LSGS_NUM'] > df_merge['FTP_NUM'])
        ).map({True:'X',False:''})

        df_merge.drop(columns=['LSGS_NUM','FTP_NUM'], inplace=True)

        st.success("🎉 TC1 hoàn tất!")
        st.dataframe(df_merge.head(30))

        st.download_button("⬇ Tải TC1.xlsx", data=to_excel(df_merge), file_name="TC1.xlsx")


# =============================================================
# ----------------------------- TC2 ----------------------------
# =============================================================
with tab2:
    st.header("🟡 TC2 – Xếp hạng KH")

    ckh_files = st.file_uploader("📂 Upload file CKH", accept_multiple_files=True, key="tc2_ckh")
    kkh_files = st.file_uploader("📂 Upload file KKH", accept_multiple_files=True, key="tc2_kkh")

    chi_nhanh_tc2 = st.text_input("Nhập SOL TC2:").strip().upper()

    if st.button("🚀 Chạy TC2"):

        if not ckh_files or not kkh_files:
            st.error("⚠ Thiếu file CKH hoặc KKH!")
            st.stop()

        cols_needed = [
            'BRCD','DEPTCD','CUST_TYPE','CUSTSEQ','NMLOC','BIRTH_DAY','IDXACNO',
            'SCHM_NAME','TERM_DAYS','GL_SUB','CCYCD','CURBAL_NT','CURBAL_VN',
            'OPNDT_FIRST','OPNDT_EFFECT','MATDT','LS_GHISO','LS_CONG_BO',
            'PROMO_CD','KH_VIP','CIF_OPNDT'
        ]

        df_ckh2 = pd.concat([read_excel_auto(f)[cols_needed] for f in ckh_files], ignore_index=True)
        df_kkh2 = pd.concat([read_excel_auto(f)[cols_needed] for f in kkh_files], ignore_index=True)

        df_ckh2 = df_ckh2[df_ckh2['BRCD'].str.upper().str.contains(chi_nhanh_tc2)]
        df_kkh2 = df_kkh2[df_kkh2['BRCD'].str.upper().str.contains(chi_nhanh_tc2)]

        df = pd.concat([df_ckh2, df_kkh2], ignore_index=True)

        df['CURBAL_VN'] = pd.to_numeric(df['CURBAL_VN'].str.replace(',',''), errors='coerce')

        df_sum = df.groupby('CUSTSEQ', as_index=False)['CURBAL_VN'].sum()
        df_sum.columns = ['CUSTSEQ','SỐ DƯ']

        df2 = df.drop_duplicates(subset='CUSTSEQ').merge(df_sum, on='CUSTSEQ')

        df2['BIRTH_DAY'] = pd.to_datetime(df2['BIRTH_DAY'], errors='coerce', dayfirst=True)

        today = pd.Timestamp.today()
        df2['ĐỘ TUỔI'] = df2.apply(
            lambda r: today.year - r['BIRTH_DAY'].year if (r['CUST_TYPE']=='KHCN' and pd.notnull(r['BIRTH_DAY'])) else None,
            axis=1
        )

        df2['RANK'] = df2.groupby('CUST_TYPE')['SỐ DƯ'].rank(method='min', ascending=False)

        st.success("🎉 TC2 hoàn tất!")
        st.dataframe(df2.head(30))

        st.download_button("⬇ Tải TC2.xlsx", data=to_excel(df2), file_name="TC2.xlsx")


# =============================================================
# ----------------------------- TC3 ----------------------------
# =============================================================
with tab3:
    st.header("🟣 TC3 – Gửi rút 1–7 ngày")

    tc3_file = st.file_uploader("📂 Upload file TC3 (MỤC 11-4)", accept_multiple_files=False)
    sol = st.text_input("Nhập SOL TC3:").strip().upper()

    if st.button("🚀 Chạy TC3"):

        df = read_excel_auto(tc3_file, dtype=str)

        df = df[df['SOL_ID'].str.upper().str.contains(sol)]

        df['NGAY_HACH_TOAN'] = pd.to_datetime(df['NGAY_HACH_TOAN'], errors='coerce')
        df['ACCT_OPN_DATE'] = pd.to_datetime(df['ACCT_OPN_DATE'], errors='coerce')
        df['PART_CLOSE_AMT'] = pd.to_numeric(df['PART_CLOSE_AMT'].str.replace(',',''), errors='coerce')

        df['CHENH_LECH_NGAY'] = (df['NGAY_HACH_TOAN'] - df['ACCT_OPN_DATE']).dt.days

        df['MO_RUT_CUNG_NGAY'] = df['CHENH_LECH_NGAY'].apply(lambda x: 'X' if x == 0 else '')
        df['MO_RUT_1_3_NGAY'] = df['CHENH_LECH_NGAY'].apply(lambda x: 'X' if 0 < x <= 3 else '')
        df['MO_RUT_4_7_NGAY'] = df['CHENH_LECH_NGAY'].apply(lambda x: 'X' if 4 <= x <= 7 else '')

        df['GD_LON_HON_1TY'] = df['PART_CLOSE_AMT'].apply(lambda x: 'X' if x > 1_000_000_000 else '')

        today = pd.to_datetime(datetime.today().date())
        df['TRONG_THOI_HIEU_CAMERA'] = df['NGAY_HACH_TOAN'].apply(
            lambda x: 'X' if pd.notna(x) and (today - x).days <= 90 else ''
        )

        st.success("🎉 TC3 hoàn tất!")
        st.dataframe(df.head(20))

        st.download_button("⬇ Tải TC3.xlsx", data=to_excel(df), file_name="TC3.xlsx")
