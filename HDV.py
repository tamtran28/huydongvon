import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime

# =========================================================
# HÀM HỖ TRỢ
# =========================================================

# Xuất DataFrame ra file Excel (bytes)
def to_excel(df, sheet_name="Sheet1"):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine="xlsxwriter")
    df.to_excel(writer, index=False, sheet_name=sheet_name)
    writer.close()
    return output.getvalue()

# Đọc Excel tự động engine theo đuôi file
def read_excel_auto(file, usecols=None, dtype=str):
    """
    Tự xác định engine theo đuôi file:
    - .xls  -> xlrd  (cần xlrd==1.2.0)
    - .xlsx -> openpyxl
    """
    name = file.name if hasattr(file, "name") else str(file)
    name = name.lower()

    if name.endswith(".xls"):
        return pd.read_excel(file, usecols=usecols, dtype=dtype, engine="xlrd")
    else:
        return pd.read_excel(file, usecols=usecols, dtype=dtype, engine="openpyxl")


# =========================================================
# GIAO DIỆN CHÍNH
# =========================================================

st.title("📊 HỆ THỐNG KIỂM TRA HDV – TC1 / TC2 / TC3")
st.markdown("Ứng dụng tổng hợp kiểm tra **Huy động vốn**: TC1 – TC2 – TC3 trên dữ liệu HDV.")

tab1, tab2, tab3 = st.tabs([
    "🔵 TC1 – HDV / FTP / Lãi suất thực trả",
    "🟡 TC2 – Xếp hạng KH & Số dư",
    "🟣 TC3 – Gửi rút trong 7 ngày"
])


# =========================================================
# TAB 1 – TC1
# =========================================================
with tab1:
    st.header("🔵 TC1 – Ghép HDV – FTP – Lãi suất thực trả")

    hdv_files = st.file_uploader(
        "📂 Upload nhiều file HDV CKH (*.xls / *.xlsx)",
        accept_multiple_files=True
    )
    ftp_files = st.file_uploader(
        "📂 Upload nhiều file FTP (*.xls / *.xlsx)",
        accept_multiple_files=True
    )
    tt_file = st.file_uploader(
        "📂 Upload file Lãi suất thực trả (*.xls / *.xlsx)",
        accept_multiple_files=False
    )

    chi_nhanh_tc1 = st.text_input(
        "Nhập tên chi nhánh hoặc mã SOL (VD: HANOI hoặc 001) cho TC1:"
    ).strip().upper()

    run_tc1 = st.button("🚀 Chạy TC1")

    if run_tc1:
        # Kiểm tra đủ file
        if not hdv_files or not ftp_files or not tt_file:
            st.error("⚠ Vui lòng upload đầy đủ file HDV, FTP và Lãi suất thực trả!")
            st.stop()

        st.info("⏳ Đang xử lý dữ liệu TC1...")

        # ---- 1. Đọc HDV CKH ----
        cols_ckh = [
            'BRCD', 'DEPTCD', 'CUST_TYPE', 'NMLOC', 'CUSTSEQ', 'BIRTH_DAY', 'IDXACNO',
            'SCHM_NAME', 'TERM_DAYS', 'GL_SUB', 'CCYCD', 'CURBAL_NT', 'CURBAL_VN',
            'OPNDT_FIRST', 'OPNDT_EFFECT', 'MATDT', 'LS_GHISO', 'LS_CONG_BO',
            'PROMO_CD', 'KH_VIP', 'CIF_OPNDT', 'DP_MTHS', 'DP_DAYS',
            'PROMO_NM', 'PHANKHUC_KH'
        ]

        df_ckh = pd.concat(
            [read_excel_auto(f, usecols=cols_ckh) for f in hdv_files],
            ignore_index=True
        )

        # ---- 2. Đọc FTP ----
        cols_ftp = ['CUSTSEQ', 'NMLOC', 'IDXACNO', 'KY_HAN', 'LS_FTP']

        df_ftp = pd.concat(
            [read_excel_auto(f, usecols=cols_ftp) for f in ftp_files],
            ignore_index=True
        )

        # ---- 3. Đọc Lãi suất thực trả ----
        df_tt = read_excel_auto(tt_file, usecols=['Số tài khoản', 'Lãi suất thực trả'])
        df_tt = df_tt.rename(columns={
            'Số tài khoản': 'IDXACNO',
            'Lãi suất thực trả': 'LS_THUC_TRA'
        })
        df_tt['IDXACNO'] = df_tt['IDXACNO'].astype(str)

        # ---- 4. Lọc theo chi nhánh BRCD ----
        if chi_nhanh_tc1:
            df_filtered = df_ckh[
                df_ckh['BRCD'].astype(str).str.upper().str.contains(chi_nhanh_tc1)
            ]
        else:
            df_filtered = df_ckh.copy()

        st.success(f"📌 Số dòng sau khi lọc chi nhánh (TC1) '{chi_nhanh_tc1}': {len(df_filtered)}")

        # ---- 5. Merge FTP theo IDXACNO ----
        df_ftp_small = df_ftp[['IDXACNO', 'LS_FTP']].drop_duplicates()
        df_merge = df_filtered.merge(df_ftp_small, on='IDXACNO', how='left')

        # ---- 6. Merge Lãi suất thực trả ----
        df_merge = df_merge.merge(df_tt, on='IDXACNO', how='left')

        # ---- 7. Tính các cột điều kiện ----
        # (3) LSGS ≠ LSCB
        df_merge['LSGS ≠ LSCB'] = (
            df_merge['LS_GHISO'] != df_merge['LS_CONG_BO']
        ).map({True: 'X', False: ''})

        # (4) Không có LS trình duyệt
        df_merge['Không có LS trình duyệt'] = df_merge['LS_THUC_TRA'].isna().map({True: 'X', False: ''})

        # (5) LSGS > FTP
        # Ép kiểu số để so sánh
        def to_float_safe(x):
            try:
                return float(str(x).replace(',', '').strip())
            except:
                return np.nan

        df_merge['LS_GHISO_NUM'] = df_merge['LS_GHISO'].apply(to_float_safe)
        df_merge['LS_FTP_NUM'] = df_merge['LS_FTP'].apply(to_float_safe)

        df_merge['LSGS > FTP'] = (
            df_merge['LS_GHISO_NUM'].notna() &
            df_merge['LS_FTP_NUM'].notna() &
            (df_merge['LS_GHISO_NUM'] > df_merge['LS_FTP_NUM'])
        ).map({True: 'X', False: ''})

        df_merge.drop(columns=['LS_GHISO_NUM', 'LS_FTP_NUM'], inplace=True)

        # ---- 8. Hiển thị & tải file ----
        st.success("🎉 ĐÃ XỬ LÝ XONG TC1!")
        st.dataframe(df_merge.head(30))

        st.download_button(
            label="⬇ Tải file kết quả TC1",
            data=to_excel(df_merge, sheet_name="TC1"),
            file_name="Ket_qua_TC1.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# =========================================================
# TAB 2 – TC2
# =========================================================
with tab2:
    st.header("🟡 TC2 – Xếp hạng KH theo số dư, VIP & Độ tuổi")

    ckh_files_tc2 = st.file_uploader(
        "📂 Upload các file HDV_CHITIET_CKH_*.xls(x)",
        accept_multiple_files=True,
        key="ckh_tc2"
    )
    kkh_files_tc2 = st.file_uploader(
        "📂 Upload các file HDV_CHITIET_KKH_*.xls(x)",
        accept_multiple_files=True,
        key="kkh_tc2"
    )

    chi_nhanh_tc2 = st.text_input(
        "Nhập tên chi nhánh hoặc mã SOL cho TC2 (lọc theo BRCD):"
    ).strip().upper()

    run_tc2 = st.button("🚀 Chạy TC2")

    if run_tc2:
        if not ckh_files_tc2 or not kkh_files_tc2:
            st.error("⚠ Vui lòng upload cả file CKH và KKH cho TC2!")
            st.stop()

        st.info("⏳ Đang đọc & xử lý dữ liệu TC2...")

        cols_needed = [
            'BRCD', 'DEPTCD', 'CUST_TYPE', 'CUSTSEQ', 'NMLOC', 'BIRTH_DAY', 'IDXACNO',
            'SCHM_NAME', 'TERM_DAYS', 'GL_SUB', 'CCYCD', 'CURBAL_NT', 'CURBAL_VN',
            'OPNDT_FIRST', 'OPNDT_EFFECT', 'MATDT', 'LS_GHISO', 'LS_CONG_BO',
            'PROMO_CD', 'KH_VIP', 'CIF_OPNDT'
        ]

        # Đọc & gộp CKH
        df_ckh_tc2 = pd.concat(
            [read_excel_auto(f, dtype=str)[cols_needed] for f in ckh_files_tc2],
            ignore_index=True
        )

        # Đọc & gộp KKH
        df_kkh_tc2 = pd.concat(
            [read_excel_auto(f, dtype=str)[cols_needed] for f in kkh_files_tc2],
            ignore_index=True
        )

        # Lọc theo chi nhánh (BRCD)
        if chi_nhanh_tc2:
            df_ckh_filtered = df_ckh_tc2[
                df_ckh_tc2['BRCD'].astype(str).str.upper().str.contains(chi_nhanh_tc2)
            ]
            df_kkh_filtered = df_kkh_tc2[
                df_kkh_tc2['BRCD'].astype(str).str.upper().str.contains(chi_nhanh_tc2)
            ]
        else:
            df_ckh_filtered = df_ckh_tc2.copy()
            df_kkh_filtered = df_kkh_tc2.copy()

        # Gộp thành df_merge
        df_merge_tc2 = pd.concat([df_kkh_filtered, df_ckh_filtered], ignore_index=True)

        # Chuyển BIRTH_DAY sang datetime (dayfirst)
        df_merge_tc2['BIRTH_DAY'] = pd.to_datetime(
            df_merge_tc2['BIRTH_DAY'], errors='coerce', dayfirst=True
        )

        # Chuyển CURBAL_VN sang số
        df_merge_tc2['CURBAL_VN'] = pd.to_numeric(
            df_merge_tc2['CURBAL_VN'].str.replace(',', ''), errors='coerce'
        )

        # ---------- Tính tổng số dư theo CIF ----------
        df_sum = (
            df_merge_tc2.groupby('CUSTSEQ', as_index=False)['CURBAL_VN']
            .sum()
            .rename(columns={'CURBAL_VN': 'SỐ DƯ'})
        )

        # Gộp số dư về 1 dòng / CIF
        df_tonghop = df_merge_tc2.drop_duplicates(subset='CUSTSEQ').merge(
            df_sum, on='CUSTSEQ', how='left'
        )

        # ---------- Tính độ tuổi cho KHCN ----------
        today = pd.Timestamp('today').normalize()

        mask_khcn = df_tonghop['CUST_TYPE'] == 'KHCN'
        df_tonghop.loc[mask_khcn, 'ĐỘ TUỔI'] = df_tonghop.loc[mask_khcn, 'BIRTH_DAY'].apply(
            lambda x: (
                today.year - x.year
                - ((today.month, today.day) < (x.month, x.day))
            ) if pd.notnull(x) else None
        )

        # ---------- Xếp hạng số dư theo từng loại KH ----------
        df_tonghop['RANK_RAW'] = df_tonghop.groupby('CUST_TYPE')['SỐ DƯ'].rank(
            method='min', ascending=False
        )

        # Tạo các cột TOP (KHDN / KHCN)
        df_tonghop['TOP10_KHDN'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHDN' and pd.notna(x['RANK_RAW']) and x['RANK_RAW'] <= 10 else '',
            axis=1
        )
        df_tonghop['TOP15_KHDN'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHDN' and pd.notna(x['RANK_RAW']) and x['RANK_RAW'] <= 15 else '',
            axis=1
        )
        df_tonghop['TOP20_KHDN'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHDN' and pd.notna(x['RANK_RAW']) and x['RANK_RAW'] <= 20 else '',
            axis=1
        )

        df_tonghop['TOP10_KHCN'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHCN' and pd.notna(x['RANK_RAW']) and x['RANK_RAW'] <= 10 else '',
            axis=1
        )
        df_tonghop['TOP15_KHCN'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHCN' and pd.notna(x['RANK_RAW']) and x['RANK_RAW'] <= 15 else '',
            axis=1
        )
        df_tonghop['TOP20_KHCN'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHCN' and pd.notna(x['RANK_RAW']) and x['RANK_RAW'] <= 20 else '',
            axis=1
        )

        # RANK hiển thị: chỉ giữ đến 20
        df_tonghop['RANK'] = df_tonghop['RANK_RAW'].apply(
            lambda x: int(x) if pd.notna(x) and x <= 20 else ''
        )

        # ---------- Đánh dấu VIP, tuổi đặc biệt ----------
        df_tonghop['VIP_KHDN'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHDN' and x['KH_VIP'] != 'General' else '',
            axis=1
        )
        df_tonghop['VIP_KHCN'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHCN' and x['KH_VIP'] != 'General' else '',
            axis=1
        )

        df_tonghop['>70_TUOI'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHCN'
            and x['ĐỘ TUỔI'] is not None
            and x['ĐỘ TUỔI'] >= 70 else '',
            axis=1
        )
        df_tonghop['<15_TUOI'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHCN'
            and x['ĐỘ TUỔI'] is not None
            and x['ĐỘ TUỔI'] < 15 else '',
            axis=1
        )
        df_tonghop['15_18_TUOI'] = df_tonghop.apply(
            lambda x: 'X' if x['CUST_TYPE'] == 'KHCN'
            and x['ĐỘ TUỔI'] is not None
            and 15 <= x['ĐỘ TUỔI'] < 18 else '',
            axis=1
        )

        # ---------- Đổi tên & chọn cột như bạn đã code ----------
        df_final_tc2 = df_tonghop.rename(columns={
            'BRCD': 'SOL',
            'CUST_TYPE': 'LOAI KH',
            'CUSTSEQ': 'CIF',
            'NMLOC': 'HO TEN',
            'BIRTH_DAY': 'NGAY SINH/NGAY TL',
            'KH_VIP': 'KH VIP'
        })[
            [
                'SOL', 'LOAI KH', 'CIF', 'HO TEN', 'NGAY SINH/NGAY TL', 'KH VIP',
                'SỐ DƯ', 'RANK', 'ĐỘ TUỔI',
                'TOP10_KHDN', 'TOP15_KHDN', 'TOP20_KHDN', 'VIP_KHDN',
                'TOP10_KHCN', 'TOP15_KHCN', 'TOP20_KHCN', 'VIP_KHCN',
                '>70_TUOI', '<15_TUOI', '15_18_TUOI'
            ]
        ]

        # Sắp xếp theo loại KH & số dư
        df_final_tc2 = df_final_tc2.sort_values(
            by=['LOAI KH', 'SỐ DƯ'],
            ascending=[True, False]
        )

        st.success("🎉 ĐÃ XỬ LÝ XONG TC2!")
        st.dataframe(df_final_tc2.head(30))

        st.download_button(
            label="⬇ Tải file TC2_HDV.xlsx",
            data=to_excel(df_final_tc2, sheet_name="TC2"),
            file_name="TC2_HDV.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# =========================================================
# TAB 3 – TC3
# =========================================================
with tab3:
    st.header("🟣 TC3 – Gửi rút 1–7 ngày, giao dịch lớn, thời hiệu camera")

    tc3_file = st.file_uploader(
        "📂 Upload file Mục 11-4 SOL (TC3) (*.xls / *.xlsx)",
        accept_multiple_files=False
    )

    chi_nhanh_tc3 = st.text_input(
        "Nhập SOL_ID cần lọc (VD: 001):"
    ).strip().upper()

    run_tc3 = st.button("🚀 Chạy TC3")

    if run_tc3:
        if not tc3_file:
            st.error("⚠ Vui lòng upload file TC3!")
            st.stop()

        st.info("⏳ Đang xử lý TC3...")

        # Đọc file TC3
        df_tc3 = read_excel_auto(tc3_file, dtype=str)

        # Lọc theo SOL_ID
        if 'SOL_ID' not in df_tc3.columns:
            st.error("⚠ File TC3 không có cột 'SOL_ID'!")
            st.stop()

        if chi_nhanh_tc3:
            df_tc3 = df_tc3[
                df_tc3['SOL_ID'].astype(str).str.upper().str.contains(chi_nhanh_tc3)
            ]

        # Chuyển kiểu dữ liệu
        df_tc3['NGAY_HACH_TOAN'] = pd.to_datetime(
            df_tc3['NGAY_HACH_TOAN'], errors='coerce'
        )
        df_tc3['ACCT_OPN_DATE'] = pd.to_datetime(
            df_tc3['ACCT_OPN_DATE'], errors='coerce'
        )

        df_tc3['PART_CLOSE_AMT'] = pd.to_numeric(
            df_tc3['PART_CLOSE_AMT'].str.replace(',', ''), errors='coerce'
        )

        # Tính chênh lệch ngày
        df_tc3['CHENH_LECH_NGAY'] = (
            df_tc3['NGAY_HACH_TOAN'] - df_tc3['ACCT_OPN_DATE']
        ).dt.days

        # (2) Mở & rút cùng ngày
        df_tc3['MO_RUT_CUNG_NGAY'] = df_tc3['CHENH_LECH_NGAY'].apply(
            lambda x: 'X' if x == 0 else ''
        )

        # (3) Rút trong 1–3 ngày
        df_tc3['MO_RUT_1_3_NGAY'] = df_tc3['CHENH_LECH_NGAY'].apply(
            lambda x: 'X' if x is not None and pd.notna(x) and 0 < x <= 3 else ''
        )

        # (4) Rút trong 4–7 ngày
        df_tc3['MO_RUT_4_7_NGAY'] = df_tc3['CHENH_LECH_NGAY'].apply(
            lambda x: 'X' if x is not None and pd.notna(x) and 4 <= x <= 7 else ''
        )

        # (5) Giao dịch lớn > 1 tỷ
        df_tc3['GD_LON_HON_1TY'] = df_tc3['PART_CLOSE_AMT'].apply(
            lambda x: 'X' if pd.notna(x) and x > 1_000_000_000 else ''
        )

        # (6) Trong thời hiệu camera (90 ngày gần nhất)
        today = pd.to_datetime(datetime.today().date())

        df_tc3['TRONG_THOI_HIEU_CAMERA'] = df_tc3['NGAY_HACH_TOAN'].apply(
            lambda x: 'X' if pd.notnull(x) and (today - x).days <= 90 else ''
        )

        st.success("🎉 ĐÃ XỬ LÝ XONG TC3!")
        st.dataframe(df_tc3.head(30))

        st.download_button(
            label="⬇ Tải file Ket_qua_TC3.xlsx",
            data=to_excel(df_tc3, sheet_name="TC3"),
            file_name="Ket_qua_TC3.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
