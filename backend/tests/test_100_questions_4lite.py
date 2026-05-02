"""
Smoke Test: 100 cau hoi pho tat ca file md da ingest.
Logic code follow y het test_100_questions.py, chi them chi so target_hit.

Tieu chi danh gia (giong smoke test 20):
- answered: bot tra loi co noi dung, khong fallback "khong co du lieu"
- has_citation: co phan "Can cu phap ly" cuoi
- target_hit: so hieu van ban muc tieu xuat hien trong response (tru cac case informational-only
  voi target_id=None — file hon hop/random name, khong tinh vao target-hit rate)

Cach chay:
  Docker:  docker compose exec backend python /app/tests/test_100_questions_4lite.py
  Local:   cd backend && python tests/test_100_questions_4lite.py
"""

import json
import os
import sys
import time
import requests
from datetime import datetime

# Backend API URL (trong Docker container goi localhost, ngoai Docker goi localhost:8088)
API_URL = os.environ.get("TEST_API_URL", "http://localhost:8088/api/chat")

# 100 cau hoi pho tat ca file md (bo cau hoi goc tu test_100_questions.py, them truong target_id)
# target_id: so hieu van ban (None voi cac file hop nhat / random name -> informational only)
QUESTIONS = [
    # === A. GIAO DUC (45 cau) ===
    {"id": 1, "question": "con toi 5 tuoi chau hoc duoc truong nao",
     "target_docs": ["Luật-43-2019-QH14.md"], "target_id": "43/2019/QH14", "group": "Giao duc"},
    {"id": 2, "question": "tre may tuoi thi bat dau di hoc lop 1",
     "target_docs": ["Luật-43-2019-QH14.md"], "target_id": "43/2019/QH14", "group": "Giao duc"},
    {"id": 3, "question": "con toi bi truong tu choi nhan vao hoc thi khieu nai o dau",
     "target_docs": ["Luật-43-2019-QH14.md"], "target_id": "43/2019/QH14", "group": "Giao duc"},
    {"id": 4, "question": "hoc sinh tieu hoc co phai dong hoc phi khong",
     "target_docs": ["Luật-43-2019-QH14.md"], "target_id": "43/2019/QH14", "group": "Giao duc"},
    {"id": 5, "question": "pho cap giao duc la gi va ap dung cho cap nao",
     "target_docs": ["Luật-43-2019-QH14.md", "22_VBHN-VPQH_651354.md"], "target_id": "43/2019/QH14", "group": "Giao duc"},
    {"id": 6, "question": "con toi khong duoc len lop thi lam sao",
     "target_docs": ["Luật-43-2019-QH14.md"], "target_id": "43/2019/QH14", "group": "Giao duc"},
    {"id": 7, "question": "truong tu thuc voi truong cong khac nhau cho nao ve mat phap ly",
     "target_docs": ["Luật-43-2019-QH14.md"], "target_id": "43/2019/QH14", "group": "Giao duc"},
    {"id": 8, "question": "dieu kien de duoc thi dai hoc la gi",
     "target_docs": ["Thông-tư-08-2022-TT-BGDĐT.md", "Thông-tư-44-2021-TT-BGDĐT.md"], "target_id": "08/2022/TT-BGDĐT", "group": "Giao duc"},
    {"id": 9, "question": "truong dai hoc tinh chi tieu tuyen sinh nhu the nao",
     "target_docs": ["Thông-tư-03-2022-TT-BGDĐT.md", "Thông-tư-10-2023-TT-BGDĐT.md"], "target_id": "03/2022/TT-BGDĐT", "group": "Giao duc"},
    {"id": 10, "question": "xet tuyen dai hoc nam 2025 co gi thay doi",
     "target_docs": ["Thông-tư-06-2025-TT-BGDĐT.md"], "target_id": "06/2025/TT-BGDĐT", "group": "Giao duc"},
    {"id": 11, "question": "chi tieu tuyen sinh cao dang giao duc mam non xac dinh the nao",
     "target_docs": ["Thông-tư-03-2022-TT-BGDĐT.md", "Thông-tư-10-2023-TT-BGDĐT.md"], "target_id": "03/2022/TT-BGDĐT", "group": "Giao duc"},
    {"id": 12, "question": "sinh vien hoc bao nhieu tin chi thi duoc tot nghiep",
     "target_docs": ["Thông-tư-08-2021-TT-BGDĐT.md"], "target_id": "08/2021/TT-BGDĐT", "group": "Giao duc"},
    {"id": 13, "question": "sinh vien bi dinh chi hoc tap trong truong hop nao",
     "target_docs": ["Thông-tư-08-2021-TT-BGDĐT.md"], "target_id": "08/2021/TT-BGDĐT", "group": "Giao duc"},
    {"id": 14, "question": "thoi gian dao tao dai hoc toi da la bao lau",
     "target_docs": ["Thông-tư-08-2021-TT-BGDĐT.md", "Luật số 08-2012-QH13.md"], "target_id": "08/2021/TT-BGDĐT", "group": "Giao duc"},
    {"id": 15, "question": "toi muon chuyen truong dai hoc thi can dieu kien gi",
     "target_docs": ["Thông-tư-08-2021-TT-BGDĐT.md"], "target_id": "08/2021/TT-BGDĐT", "group": "Giao duc"},
    {"id": 16, "question": "truong dai hoc co quyen tu chu nhung gi",
     "target_docs": ["Luật số 34-2018-QH14..md", "Luật số 08-2012-QH13.md"], "target_id": "34/2018/QH14", "group": "Giao duc"},
    {"id": 17, "question": "hoi dong truong dai hoc la gi va co nhiem vu gi",
     "target_docs": ["Luật số 34-2018-QH14..md"], "target_id": "34/2018/QH14", "group": "Giao duc"},
    {"id": 18, "question": "dieu kien de hoc thac si la gi",
     "target_docs": ["Nghị-định-99-2019-NĐ-CP.md", "99.signed.md"], "target_id": "99/2019/NĐ-CP", "group": "Giao duc"},
    {"id": 19, "question": "hoc tien si mat bao lau",
     "target_docs": ["Nghị-định-99-2019-NĐ-CP.md", "99.signed.md"], "target_id": "99/2019/NĐ-CP", "group": "Giao duc"},
    {"id": 20, "question": "giang vien can trinh do gi de duoc day dai hoc",
     "target_docs": ["Thông tư số 25-2021-TT-BGDĐT .md", "Luật số 08-2012-QH13.md"], "target_id": "25/2021/TT-BGDĐT", "group": "Giao duc"},
    {"id": 21, "question": "truong nuoc ngoai muon mo chi nhanh tai viet nam can dieu kien gi",
     "target_docs": ["Nghị-định-86-2018-NĐ-CP.md", "Nghị-định-125-2024-NĐ-CP.md"], "target_id": "86/2018/NĐ-CP", "group": "Giao duc"},
    {"id": 22, "question": "hoc chuong trinh lien ket voi truong nuoc ngoai co duoc cap bang viet nam khong",
     "target_docs": ["Thông tư số 07-2025-TT-BGDĐT.md"], "target_id": "07/2025/TT-BGDĐT", "group": "Giao duc"},
    {"id": 23, "question": "dieu kien de mo nganh dao tao moi tai truong dai hoc la gi",
     "target_docs": ["Nghị-định-125-2024-NĐ-CP.md", "Nghị-định-99-2019-NĐ-CP.md"], "target_id": "125/2024/NĐ-CP", "group": "Giao duc"},
    {"id": 24, "question": "kiem dinh chat luong truong dai hoc la gi",
     "target_docs": ["Thông-tư-12-2017-TT-BGDĐT.md", "Thông tư 62-2012-TT-BGDĐT.md", "Quyết-định-790-QĐ-BGDĐT.md"], "target_id": "12/2017/TT-BGDĐT", "group": "Giao duc"},
    {"id": 25, "question": "truong dai hoc khong dat kiem dinh thi sao",
     "target_docs": ["Thông-tư-04-2025-TT-BGDĐT.md", "Thông-tư-13-2023-TT-BGDĐT.md"], "target_id": "04/2025/TT-BGDĐT", "group": "Giao duc"},
    {"id": 26, "question": "ai duoc lam kiem dinh vien giao duc dai hoc",
     "target_docs": ["Thông-tư-14-2022-TT-BGDĐT.md"], "target_id": "14/2022/TT-BGDĐT", "group": "Giao duc"},
    {"id": 27, "question": "bang dai hoc ghi nhung noi dung gi",
     "target_docs": ["Thông tư số 27-2019-TT-BGDĐT.md", "Thông-tư-21-2019-TT-BGDĐT.md"], "target_id": "27/2019/TT-BGDĐT", "group": "Giao duc"},
    {"id": 28, "question": "chung chi pte academic tuong duong bac nao cua khung nang luc ngoai ngu viet nam",
     "target_docs": ["Quyết-định-2383-QĐ-BGDĐT.md"], "target_id": "2383/QĐ-BGDĐT", "group": "Giao duc"},
    {"id": 29, "question": "che do lam viec cua giang vien dai hoc nhu the nao",
     "target_docs": ["Thông tư số 20-2020-TT-BGDĐT.md"], "target_id": "20/2020/TT-BGDĐT", "group": "Giao duc"},
    {"id": 30, "question": "giang vien dai hoc co phai lam nghien cuu khong",
     "target_docs": ["Thông tư số 20-2020-TT-BGDĐT.md"], "target_id": "20/2020/TT-BGDĐT", "group": "Giao duc"},
    {"id": 31, "question": "vi tri viec lam trong truong dai hoc cong lap gom nhung gi",
     "target_docs": ["Thông tư số 04-2024-TT-BGDĐT.md"], "target_id": "04/2024/TT-BGDĐT", "group": "Giao duc"},
    {"id": 32, "question": "sinh vien co duoc tham gia nghien cuu khoa hoc khong",
     "target_docs": ["Thông tư số 26-2021-TT-BGDĐT.md"], "target_id": "26/2021/TT-BGDĐT", "group": "Giao duc"},
    {"id": 33, "question": "truong dai hoc to chuc hoat dong khoa hoc cong nghe nhu the nao",
     "target_docs": ["Nghị-định-109-2022-NĐ-CP.md", "Thông-tư-09-2018-TT-BGDĐT.md"], "target_id": "109/2022/NĐ-CP", "group": "Giao duc"},
    {"id": 34, "question": "de tai khoa hoc cap bo cua bo giao duc quan ly ra sao",
     "target_docs": ["Thông-tư-11-2016-TT-BGDĐT.md"], "target_id": "11/2016/TT-BGDĐT", "group": "Giao duc"},
    {"id": 35, "question": "giai thuong khoa hoc cong nghe danh cho sinh vien la gi",
     "target_docs": ["Thông-tư-45-2020-TT-BGDĐT.md"], "target_id": "45/2020/TT-BGDĐT", "group": "Giao duc"},
    {"id": 36, "question": "truong dai hoc co duoc day truc tuyen khong",
     "target_docs": ["Thông tư số 30-2023-TT-BGDĐT.md", "Thông-tư-30-2023-TT-BGDĐT.md"], "target_id": "30/2023/TT-BGDĐT", "group": "Giao duc"},
    {"id": 37, "question": "hoc truc tuyen thi gioi han bao nhieu phan tram chuong trinh",
     "target_docs": ["Thông tư số 30-2023-TT-BGDĐT.md", "Thông-tư-30-2023-TT-BGDĐT.md"], "target_id": "30/2023/TT-BGDĐT", "group": "Giao duc"},
    {"id": 38, "question": "thu vien truong dai hoc can dat tieu chuan gi",
     "target_docs": ["Thông tư số 14-2023-TT-BGDĐT.md"], "target_id": "14/2023/TT-BGDĐT", "group": "Giao duc"},
    {"id": 39, "question": "nha giao dat danh hieu nha giao uu tu can dieu kien gi",
     "target_docs": ["21_2020_TT_BGDDT.md"], "target_id": "21/2020/TT-BGDĐT", "group": "Giao duc"},
    {"id": 40, "question": "thu tuc hanh chinh trong linh vuc giao duc dai hoc gom nhung gi",
     "target_docs": ["1134_QD-BGDDT_512062.md", "2231_QD-BGDDT_574574.md", "4022_QD-BGDDT_637691.md"], "target_id": None, "group": "Giao duc"},
    {"id": 41, "question": "chuong trinh pho cap ky nang so va chuyen doi so cho sinh vien dai hoc la gi",
     "target_docs": ["1504_QD-BGDDT_660137.md", "4740_QD-BGDDT_549856.md"], "target_id": None, "group": "Giao duc"},
    {"id": 42, "question": "tai nguyen giao duc mo trong dai hoc la gi",
     "target_docs": ["1919_KH-BGDDT_637695.md"], "target_id": None, "group": "Giao duc"},
    {"id": 43, "question": "danh muc nganh dao tao dai hoc hien nay gom nhung gi",
     "target_docs": ["Thông tư số 09-2022-TT-BGDĐT.md", "Quyết định 1596-QĐ-BGDĐT .md"], "target_id": "09/2022/TT-BGDĐT", "group": "Giao duc"},
    {"id": 44, "question": "chuan chuong trinh dao tao dai hoc duoc quy dinh nhu the nao va giao trinh ai bien soan",
     "target_docs": ["Thông-tư-17-2021-TT-BGDĐT.md", "Thông-tư-35-2021-TT-BGDĐT.md"], "target_id": "17/2021/TT-BGDĐT", "group": "Giao duc"},
    {"id": 45, "question": "luat giao duc hien hanh quy dinh nhung gi ve quyen cua nguoi hoc va chuan co so giao duc",
     "target_docs": ["22_VBHN-VPQH_651354.md", "Thông tư số 46-2021-TT-BGDĐT.md", "Thông-tư-02-2022-TT-BGDĐT.md", "Thông tư số 01-2024-TT-BGDĐT.md"], "target_id": None, "group": "Giao duc"},

    # === B. BAO HIEM XA HOI (15 cau) ===
    {"id": 46, "question": "toi la lao dong tu do thi co dong bao hiem xa hoi duoc khong",
     "target_docs": ["Luật-41-2024-QH15.md"], "target_id": "41/2024/QH15", "group": "BHXH"},
    {"id": 47, "question": "dong bao hiem xa hoi bao nhieu nam thi duoc nghi huu",
     "target_docs": ["Luật-41-2024-QH15.md"], "target_id": "41/2024/QH15", "group": "BHXH"},
    {"id": 48, "question": "nguoi giup viec gia dinh co phai dong bhxh khong",
     "target_docs": ["Luật-41-2024-QH15.md"], "target_id": "41/2024/QH15", "group": "BHXH"},
    {"id": 49, "question": "toi muon rut bao hiem xa hoi mot lan thi can dieu kien gi",
     "target_docs": ["Luật-41-2024-QH15.md"], "target_id": "41/2024/QH15", "group": "BHXH"},
    {"id": 50, "question": "muc dong bao hiem xa hoi bat buoc la bao nhieu phan tram luong",
     "target_docs": ["Nghị-định-158-2025-NĐ-CP.md"], "target_id": "158/2025/NĐ-CP", "group": "BHXH"},
    {"id": 51, "question": "che do thai san bhxh bat buoc duoc huong nhung gi",
     "target_docs": ["Nghị-định-158-2025-NĐ-CP.md", "Luật-41-2024-QH15.md"], "target_id": "158/2025/NĐ-CP", "group": "BHXH"},
    {"id": 52, "question": "dong bhxh tu nguyen muc thap nhat la bao nhieu",
     "target_docs": ["Nghị-định-159-2025-NĐ-CP.md"], "target_id": "159/2025/NĐ-CP", "group": "BHXH"},
    {"id": 53, "question": "dong bhxh tu nguyen thi duoc huong nhung che do nao",
     "target_docs": ["Nghị-định-159-2025-NĐ-CP.md"], "target_id": "159/2025/NĐ-CP", "group": "BHXH"},
    {"id": 54, "question": "nguoi gia khong co luong huu thi co duoc ho tro gi khong",
     "target_docs": ["Nghị-định-176-2025-NĐ-CP.md"], "target_id": "176/2025/NĐ-CP", "group": "BHXH"},
    {"id": 55, "question": "tro cap huu tri xa hoi la gi va ai duoc huong",
     "target_docs": ["Nghị-định-176-2025-NĐ-CP.md"], "target_id": "176/2025/NĐ-CP", "group": "BHXH"},
    {"id": 56, "question": "toi co the dong bao hiem xa hoi truc tuyen khong",
     "target_docs": ["Nghị-định-164-2025-NĐ-CP-.md"], "target_id": "164/2025/NĐ-CP", "group": "BHXH"},
    {"id": 57, "question": "cong ty tron dong bao hiem cho nhan vien thi bi xu phat nhu the nao",
     "target_docs": ["Nghị-định-274-2025-NĐ-CP.md"], "target_id": "274/2025/NĐ-CP", "group": "BHXH"},
    {"id": 58, "question": "quy bao hiem xa hoi duoc quan ly su dung va dau tu nhu the nao",
     "target_docs": ["Nghị-định-233-2025-NĐ-CP.md", "233_2025_ND-CP_670873.md", "Nghị-định-212-2025-NĐ-CP.md", "212_2025_ND-CP_666742.md"], "target_id": "233/2025/NĐ-CP", "group": "BHXH"},
    {"id": 59, "question": "vi pham luat lao dong va bao hiem xa hoi bi phat bao nhieu tien",
     "target_docs": ["Nghị-định-28-2020-NĐ-CP.md"], "target_id": "28/2020/NĐ-CP", "group": "BHXH"},
    {"id": 60, "question": "he thong chi tieu thong ke nganh bao hiem xa hoi gom nhung gi",
     "target_docs": ["627183.md"], "target_id": None, "group": "BHXH"},

    # === C. BAO HIEM Y TE (12 cau) ===
    # NOTE: target_id da widen sang multi-valid 2026-05-02 — nguyen target_id "25/2018/QH14" sai (la Luat To cao,
    # khong phai BHYT). He thong luat BHYT thuc te: Luat 51/2024/QH15 (sua doi BHYT), NĐ 146/2018, NĐ 188/2025
    # (chi tiet moi), NĐ 02/2025 + 75/2023 (sua doi 146), TT 01/2025/TT-BYT (huong dan).
    {"id": 61, "question": "toi chua co bao hiem y te thi mua o dau",
     "target_docs": ["Luật-51-2024-QH15.md", "Nghị-định-188-2025-NĐ-CP.md", "Nghị-định-146-2018-NĐ-CP.md"],
     "target_id": ["188/2025/NĐ-CP", "146/2018/NĐ-CP", "51/2024/QH15"], "group": "BHYT"},
    {"id": 62, "question": "bao hiem y te chi tra nhung gi khi di kham benh",
     "target_docs": ["Luật-51-2024-QH15.md", "Nghị-định-188-2025-NĐ-CP.md"],
     "target_id": ["51/2024/QH15", "188/2025/NĐ-CP", "146/2018/NĐ-CP"], "group": "BHYT"},
    {"id": 63, "question": "the bao hiem y te het han thi lam lai nhu the nao",
     "target_docs": ["Nghị-định-188-2025-NĐ-CP.md", "Nghị-định-146-2018-NĐ-CP.md"],
     "target_id": ["188/2025/NĐ-CP", "146/2018/NĐ-CP", "51/2024/QH15"], "group": "BHYT"},
    {"id": 64, "question": "kham benh trai tuyen thi bao hiem chi tra bao nhieu phan tram",
     "target_docs": ["Luật-51-2024-QH15.md", "Nghị-định-188-2025-NĐ-CP.md"],
     "target_id": ["51/2024/QH15", "188/2025/NĐ-CP", "146/2018/NĐ-CP"], "group": "BHYT"},
    {"id": 65, "question": "tre em duoi 6 tuoi co duoc cap the bao hiem y te mien phi khong",
     "target_docs": ["Nghị-định-146-2018-NĐ-CP.md", "Nghị-định-188-2025-NĐ-CP.md"],
     "target_id": ["146/2018/NĐ-CP", "188/2025/NĐ-CP", "51/2024/QH15"], "group": "BHYT"},
    {"id": 66, "question": "nguoi ngheo co duoc nha nuoc ho tro mua bao hiem y te khong",
     "target_docs": ["Nghị-định-146-2018-NĐ-CP.md", "Nghị-định-75-2023-NĐ-CP.md"],
     "target_id": ["146/2018/NĐ-CP", "75/2023/NĐ-CP", "188/2025/NĐ-CP"], "group": "BHYT"},
    {"id": 67, "question": "muc dong bao hiem y te hien nay la bao nhieu",
     "target_docs": ["Nghị-định-02-2025-NĐ-CP.md", "Nghị-định-146-2018-NĐ-CP.md", "Nghị-định-188-2025-NĐ-CP.md"],
     "target_id": ["146/2018/NĐ-CP", "188/2025/NĐ-CP", "02/2025/NĐ-CP", "51/2024/QH15"], "group": "BHYT"},
    {"id": 68, "question": "benh nhan ung thu duoc bao hiem y te chi tra nhu the nao",
     "target_docs": ["Nghị-định-188-2025-NĐ-CP.md"],
     "target_id": ["188/2025/NĐ-CP", "51/2024/QH15"], "group": "BHYT"},
    {"id": 69, "question": "danh muc thuoc bao hiem y te gom nhung loai nao",
     "target_docs": ["Nghị-định-188-2025-NĐ-CP.md", "Thông-tư-01-2025-TT-BYT.md"],
     "target_id": ["188/2025/NĐ-CP", "01/2025/TT-BYT"], "group": "BHYT"},
    {"id": 70, "question": "quy trinh kham chua benh bao hiem y te dien ra nhu the nao",
     "target_docs": ["Thông-tư-01-2025-TT-BYT.md", "Nghị-định-188-2025-NĐ-CP.md"],
     "target_id": ["01/2025/TT-BYT", "188/2025/NĐ-CP", "146/2018/NĐ-CP"], "group": "BHYT"},
    {"id": 71, "question": "co so y te nao duoc kham bao hiem y te",
     "target_docs": ["Thông-tư-01-2025-TT-BYT.md", "Nghị-định-188-2025-NĐ-CP.md"],
     "target_id": ["01/2025/TT-BYT", "188/2025/NĐ-CP"], "group": "BHYT"},
    {"id": 72, "question": "chuyen vien bao hiem y te can thu tuc gi",
     "target_docs": ["Thông-tư-01-2025-TT-BYT.md", "Nghị-định-188-2025-NĐ-CP.md", "Luật-51-2024-QH15.md"],
     "target_id": ["01/2025/TT-BYT", "188/2025/NĐ-CP", "51/2024/QH15"], "group": "BHYT"},

    # === D. VIEC LAM & LAO DONG (10 cau) ===
    {"id": 73, "question": "toi bi mat viec thi duoc ho tro gi",
     "target_docs": ["Luật-74-2025-QH15.md"], "target_id": "74/2025/QH15", "group": "Viec lam"},
    {"id": 74, "question": "bao hiem that nghiep chi tra bao nhieu tien mot thang",
     "target_docs": ["Luật-74-2025-QH15.md"], "target_id": "74/2025/QH15", "group": "Viec lam"},
    {"id": 75, "question": "dang ky lao dong la gi va co bat buoc khong",
     "target_docs": ["Luật-74-2025-QH15.md"], "target_id": "74/2025/QH15", "group": "Viec lam"},
    {"id": 76, "question": "phan biet doi xu trong tuyen dung la gi",
     "target_docs": ["Luật-74-2025-QH15.md"], "target_id": "74/2025/QH15", "group": "Viec lam"},
    {"id": 77, "question": "dieu kien de huong bao hiem that nghiep la gi",
     "target_docs": ["Nghị-định-28-2015-NĐ-CP.md"], "target_id": "28/2015/NĐ-CP", "group": "Viec lam"},
    {"id": 78, "question": "thoi gian huong tro cap that nghiep toi da bao lau",
     "target_docs": ["Nghị-định-28-2015-NĐ-CP.md", "Nghị-định-61-2020-NĐ-CP.md"], "target_id": "28/2015/NĐ-CP", "group": "Viec lam"},
    {"id": 79, "question": "nguoi lao dong bi tai nan lao dong thi duoc boi thuong the nao",
     "target_docs": ["Thông-tư-28-2015-TT-BLĐTBXH.md"], "target_id": "28/2015/TT-BLĐTBXH", "group": "Viec lam"},
    {"id": 80, "question": "hop dong lao dong phai co nhung noi dung gi",
     "target_docs": ["Thông-tư-23-2022-TT-BLĐTBXH.md"], "target_id": "23/2022/TT-BLĐTBXH", "group": "Viec lam"},
    {"id": 81, "question": "toi bi cong ty cat giam lao dong thi quyen loi cua toi la gi",
     "target_docs": ["Thông-tư-15-2023-TT-BLĐTBXH.md"], "target_id": "15/2023/TT-BLĐTBXH", "group": "Viec lam"},
    {"id": 82, "question": "chinh sach ho tro hoc nghe cho nguoi that nghiep la gi",
     "target_docs": ["Nghị-định-61-2020-NĐ-CP.md", "Luật-74-2025-QH15.md"], "target_id": "61/2020/NĐ-CP", "group": "Viec lam"},

    # === E. TAI CHINH CONG (10 cau) ===
    {"id": 83, "question": "ngan sach nha nuoc la gi va ai quyet dinh",
     "target_docs": ["Luật-83-2015-QH13.md", "Luật-89-2025-QH15.md"], "target_id": "83/2015/QH13", "group": "Tai chinh"},
    {"id": 84, "question": "boi chi ngan sach la gi",
     "target_docs": ["Luật-83-2015-QH13.md", "Luật-89-2025-QH15.md"], "target_id": "83/2015/QH13", "group": "Tai chinh"},
    {"id": 85, "question": "nguoi dan co duoc giam sat viec su dung ngan sach khong",
     "target_docs": ["Luật-83-2015-QH13.md", "Luật-89-2025-QH15.md"], "target_id": "83/2015/QH13", "group": "Tai chinh"},
    {"id": 86, "question": "doanh nghiep co bat buoc phai lam ke toan khong",
     "target_docs": ["Luật-88-2015-QH13.md"], "target_id": "88/2015/QH13", "group": "Tai chinh"},
    {"id": 87, "question": "bao cao tai chinh hang nam phai nop khi nao",
     "target_docs": ["Luật-88-2015-QH13.md"], "target_id": "88/2015/QH13", "group": "Tai chinh"},
    {"id": 88, "question": "kiem toan nha nuoc la gi va co quyen gi",
     "target_docs": ["Luật-81-2015-QH13.md"], "target_id": "81/2015/QH13", "group": "Tai chinh"},
    {"id": 89, "question": "ai bi kiem toan nha nuoc kiem tra",
     "target_docs": ["Luật-81-2015-QH13.md"], "target_id": "81/2015/QH13", "group": "Tai chinh"},
    {"id": 90, "question": "tai san cong la gi va ai duoc su dung",
     "target_docs": ["Luật-15-2017-QH14.md"], "target_id": "15/2017/QH14", "group": "Tai chinh"},
    {"id": 91, "question": "co quan nha nuoc muon mua sam tai san phai lam thu tuc gi",
     "target_docs": ["Nghị-định-186-2025-NĐ-CP.md", "Luật-15-2017-QH14.md"], "target_id": "186/2025/NĐ-CP", "group": "Tai chinh"},
    {"id": 92, "question": "xu ly tai san cong khi khong con su dung nhu the nao",
     "target_docs": ["Nghị-định-286-2025-NĐ-CP.md", "Luật-15-2017-QH14.md"], "target_id": "286/2025/NĐ-CP", "group": "Tai chinh"},

    # === F. KHIEU NAI, TO CAO (5 cau) ===
    {"id": 93, "question": "toi muon khieu nai quyet dinh cua uy ban nhan dan thi gui don o dau",
     "target_docs": ["Luật-02-2011-QH13.md", "Nghị-định-124-2020-NĐ-CP.md"], "target_id": "02/2011/QH13", "group": "Khieu nai"},
    {"id": 94, "question": "thoi hieu khieu nai la bao lau",
     "target_docs": ["Luật-02-2011-QH13.md"], "target_id": "02/2011/QH13", "group": "Khieu nai"},
    {"id": 95, "question": "toi muon to cao tham nhung thi gui don cho ai",
     "target_docs": ["Nghị-định-31-2019-NĐ-CP.md"], "target_id": "31/2019/NĐ-CP", "group": "Khieu nai"},
    {"id": 96, "question": "nguoi to cao co duoc bao ve khong",
     "target_docs": ["Nghị-định-31-2019-NĐ-CP.md"], "target_id": "31/2019/NĐ-CP", "group": "Khieu nai"},
    {"id": 97, "question": "toi muon gap lanh dao de khieu nai truc tiep thi den dau",
     "target_docs": ["Luật-136-2025-QH15.md"], "target_id": "136/2025/QH15", "group": "Khieu nai"},

    # === G. KHAC (3 cau) ===
    {"id": 98, "question": "co quan bao hiem xa hoi viet nam co chuc nang gi",
     "target_docs": ["Nghị-định-89-2020-NĐ-CP.md"], "target_id": "89/2020/NĐ-CP", "group": "Khac"},
    {"id": 99, "question": "co che tai chinh thuc hien khung trinh do quoc gia viet nam doi voi giao duc dai hoc nhu the nao",
     "target_docs": ["Nghị-định-166-2016-NĐ-CP.md", "Thông-tư-26-2022-TT-BTC.md"], "target_id": "166/2016/NĐ-CP", "group": "Khac"},
    {"id": 100, "question": "nhiem vu va huong dan cua bo giao duc cho cac truong dai hoc trong nam hoc moi la gi",
     "target_docs": ["646301.md", "4725_BGDDT-PC.md"], "target_id": None, "group": "Khac"},
]


def call_chat_api(question):
    """Goi API /api/chat va doc toan bo streaming response."""
    t_start = time.time()
    first_byte_time = None
    full_response = ""

    try:
        resp = requests.post(
            API_URL,
            json={"query": question, "history": []},
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                if first_byte_time is None:
                    first_byte_time = time.time()
                full_response += chunk

    except Exception as e:
        return {
            "response": "",
            "error": str(e),
            "fttb_s": None,
            "total_time_s": time.time() - t_start,
        }

    t_end = time.time()
    return {
        "response": full_response,
        "error": None,
        "fttb_s": round(first_byte_time - t_start, 2) if first_byte_time else None,
        "total_time_s": round(t_end - t_start, 2),
    }


def check_answered(response_text):
    """Kiem tra bot co tra loi hay tra ve 'khong tim thay du lieu'."""
    no_data_phrases = [
        "khong tim thay",
        "khong co du lieu",
        "khong the tim thay",
        "khong co thong tin",
        "xin loi",
    ]
    lower = response_text.lower()
    for phrase in no_data_phrases:
        if phrase in lower and len(response_text) < 300:
            return False
    return len(response_text.strip()) > 50


def check_citation(response_text):
    """Kiem tra co phan 'Can cu phap ly' khong. Ho tro nhieu variant dau/khong dau."""
    import unicodedata
    def remove_accents(s):
        nfkd = unicodedata.normalize('NFKD', s)
        return ''.join(c for c in nfkd if not unicodedata.combining(c))
    normalized = remove_accents(response_text.lower())
    return "can cu phap ly" in normalized


def check_target_hit(response_text, target_id):
    """Kiem tra so hieu van ban muc tieu co xuat hien trong response khong.
    target_id co the la str (1 so hieu) hoac list[str] (nhieu so hieu valid — hit neu bat ky cai nao xuat hien).
    Tra ve None neu target_id=None (informational-only case)."""
    if target_id is None:
        return None
    if isinstance(target_id, list):
        return any(t in response_text for t in target_id)
    return target_id in response_text


def run_test_suite():
    """Chay toan bo 100 cau hoi va luu ket qua."""
    print("=" * 60)
    print("SMOKE TEST: 100 cau - pho het cac file md da ingest")
    print("API: %s" % API_URL)
    print("Start: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    # Kiem tra API san sang
    try:
        health = requests.get(API_URL.replace("/api/chat", "/health"), timeout=10)
        health.raise_for_status()
        print("[OK] Backend API is healthy.\n")
    except Exception as e:
        print("[ERROR] Backend API not reachable: %s" % str(e))
        print("Make sure Docker is running: docker compose up -d")
        sys.exit(1)

    results = []
    answered_count = 0
    citation_count = 0
    target_hit_count = 0
    target_hit_total = 0  # so case co target_id (khong informational-only)
    error_count = 0
    total_time = 0

    for q in QUESTIONS:
        qid = q["id"]
        question = q["question"]
        target_id = q["target_id"]
        print("[%3d/100] %s..." % (qid, question[:60]), end=" ", flush=True)

        result = call_chat_api(question)

        if result["error"]:
            print("ERROR: %s" % result["error"][:50])
            error_count += 1
            results.append({
                "id": qid,
                "question": question,
                "group": q["group"],
                "target_docs": q["target_docs"],
                "target_id": target_id,
                "answered": False,
                "has_citation": False,
                "target_hit": None,
                "error": result["error"],
                "fttb_s": result["fttb_s"],
                "total_time_s": result["total_time_s"],
                "response_preview": "",
            })
            continue

        is_answered = check_answered(result["response"])
        has_citation = check_citation(result["response"])
        target_hit = check_target_hit(result["response"], target_id)

        if is_answered:
            answered_count += 1
        if has_citation:
            citation_count += 1
        if target_hit is not None:
            target_hit_total += 1
            if target_hit:
                target_hit_count += 1
        total_time += result["total_time_s"]

        status = "OK" if is_answered else "NO_DATA"
        cite = "+cite" if has_citation else "-cite"
        if target_hit is None:
            hit = "info"
        else:
            hit = "+hit" if target_hit else "-hit"
        print("%s %s %s (%.1fs FTTB, %.1fs total)" % (status, cite, hit, result["fttb_s"] or 0, result["total_time_s"]))

        results.append({
            "id": qid,
            "question": question,
            "group": q["group"],
            "target_docs": q["target_docs"],
            "target_id": target_id,
            "answered": is_answered,
            "has_citation": has_citation,
            "target_hit": target_hit,
            "error": None,
            "fttb_s": result["fttb_s"],
            "total_time_s": result["total_time_s"],
            "response_preview": result["response"][:500],
        })

    # Summary
    valid_count = len(results) - error_count
    avg_time = round(total_time / valid_count, 2) if valid_count > 0 else 0

    summary = {
        "run_at": datetime.now().isoformat(),
        "api_url": API_URL,
        "total_questions": len(QUESTIONS),
        "answered": answered_count,
        "no_data": valid_count - answered_count,
        "has_citation": citation_count,
        "target_hit": target_hit_count,
        "target_hit_total": target_hit_total,
        "errors": error_count,
        "avg_response_time_s": avg_time,
        "results": results,
    }

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("  Total:        %d" % len(QUESTIONS))
    if valid_count:
        print("  Answered:     %d/%d (%.1f%%)" % (answered_count, valid_count, answered_count / valid_count * 100))
        print("  Has citation: %d/%d (%.1f%%)" % (citation_count, valid_count, citation_count / valid_count * 100))
    if target_hit_total:
        print("  Target hit:   %d/%d (%.1f%%)" % (target_hit_count, target_hit_total, target_hit_count / target_hit_total * 100))
    print("  Errors:       %d" % error_count)
    print("  Avg time:     %.2fs" % avg_time)

    # Group breakdown
    groups = {}
    for r in results:
        g = r["group"]
        if g not in groups:
            groups[g] = {"total": 0, "answered": 0, "citation": 0, "hit": 0, "hit_total": 0}
        groups[g]["total"] += 1
        if r["answered"]:
            groups[g]["answered"] += 1
        if r["has_citation"]:
            groups[g]["citation"] += 1
        if r["target_hit"] is not None:
            groups[g]["hit_total"] += 1
            if r["target_hit"]:
                groups[g]["hit"] += 1

    print("\n  Per group:")
    for g, stats in groups.items():
        pct = round(stats["answered"] / stats["total"] * 100, 1)
        hit_str = ""
        if stats["hit_total"]:
            hit_str = ", %d/%d hit" % (stats["hit"], stats["hit_total"])
        print("    %-12s: %d/%d answered (%.1f%%), %d with citation%s" % (g, stats["answered"], stats["total"], pct, stats["citation"], hit_str))

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(output_dir, "test_suit_%s.json" % timestamp)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n  Results saved: %s" % output_file)
    print("=" * 60)

    return summary


if __name__ == "__main__":
    run_test_suite()
