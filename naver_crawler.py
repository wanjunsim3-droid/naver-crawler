import requests
import pandas as pd
from datetime import datetime
import time

def crawling_naver_real_estate():
    print("네이버 부동산 지식산업센터 (강서구) 매물 수집을 시작합니다...")
    print("수집조건: 상가/사무실/공장/지식산업센터 지역 내 '임대 및 분양' 매물")
    
    cortar_no = "1150000000"  # 강서구
    # K01: 지식산업센터, K02: 지식산업센터(지원), D01: 사무실, D02: 상가, E02: 공장/창고
    rlet_tp_cds = ["K01", "K02", "D01", "D02", "E02"]
    trad_tp_cd = "B1:B2:E1" # 전세, 월세, 분양권
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://m.land.naver.com/",
        "Origin": "https://m.land.naver.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive"
    }

    session = requests.Session()
    session.headers.update(headers)

    all_articles = []

    for rlet_tp in rlet_tp_cds:
        # 1. 지역 내 클러스터(lgeo) 조회
        cluster_url = f"https://m.land.naver.com/cluster/clusterList?view=atcl&cortarNo={cortar_no}&rletTpCd={rlet_tp}&tradTpCd={trad_tp_cd}&z=12&lat=37.550979&lon=126.849534"
        try:
            res = session.get(cluster_url, timeout=10)
            print(f"[{rlet_tp}] 클러스터 API 상태코드: {res.status_code}")
            if res.status_code != 200:
                print(f"[{rlet_tp}] 클러스터 목록 조회 실패 (StatusCode: {res.status_code})")
                continue
            
            data = res.json()
            # print(f"[{rlet_tp}] 클러스터 응답 데이터: {str(data)[:200]}") # Debug print
            clusters = data.get("data", {}).get("ARTICLE", [])
            print(f"[{rlet_tp}] 찾은 클러스터 개수: {len(clusters)}")
            
            if not clusters:
                print(f"[{rlet_tp}] 응답 데이터 요약: {str(data)[:500]}")
        except Exception as e:
            print(f"[{rlet_tp}] 클러스터 목록 파싱 오류: {e}")
            continue
        
        # 2. 클러스터별로 매물 상세 목록 수집
        for cluster in clusters:
            lgeo = cluster.get("lgeo")
            count = cluster.get("count", 0)
            if not lgeo:
                continue
                
            page = 1
            while True:
                list_url = f"https://m.land.naver.com/cluster/ajax/articleList?itemId={lgeo}&lgeo={lgeo}&rletTpCd={rlet_tp}&tradTpCd={trad_tp_cd}&z=12&lat=37.550979&lon=126.849534&page={page}"
                try:
                    res_list = session.get(list_url, timeout=10)
                    if page == 1:
                        print(f"  - 클러스터 {lgeo} {page}페이지 요청 (현재 누적: {len(all_articles)}건)")
                    if res_list.status_code != 200:
                        print(f"  -> 리다이렉트 여부: {res_list.is_redirect}, 최종 URL: {res_list.url}")
                        break
                    
                    list_data = res_list.json()
                    
                    if page == 1 and not list_data.get("body"):
                        print(f"  -> 응답 데이터 존재함, 그러나 body 파싱 결과: {len(list_data.get('body', []))}건 (more: {list_data.get('more', False)})")
                    
                    articles = list_data.get("body", [])
                    
                    if not articles:
                        break
                        
                    for item in articles:
                        # 매물 데이터 파싱
                        all_articles.append({
                            "매물종류": item.get("rletTpNm", rlet_tp),
                            "거래유형": item.get("tradTpNm"),
                            "건물명": item.get("atclNm"),
                            "면적(공급/전용 ㎡)": f"{item.get('spc1', '')} / {item.get('spc2', '')}",
                            "가격(보증금/월세 또는 분양가)": item.get("prcInfo"),
                            "층수": item.get("flrInfo"),
                            "상세설명": item.get("atclFetrDesc", ""),
                            "부동산명": item.get("rltrNm"),
                            "매물확인일자": item.get("cfmYmd", ""),
                            "담당자댓글": item.get("repMnprcsDesc", ""),
                            "매물번호": item.get("atclNo"),
                            "네이버부동산링크": f"https://new.land.naver.com/complexes?articleNo={item.get('atclNo')}" if item.get("atclNo") else "",
                        })
                    
                    if not list_data.get("more", False):
                        break  # 다음 페이지 없음
                        
                    page += 1
                    time.sleep(0.8)  # 차단 방지를 위해 대기 시간 늘림
                    
                except Exception as e:
                    print(f"[{rlet_tp}] 클러스터 {lgeo} - {page}페이지 읽기 오류: {e}")
                    break
                    
        print(f"[{rlet_tp}] 데이터 수집 완료. (현재까지 누적 매물: {len(all_articles)}건)")
        time.sleep(1.0)  # 종류 바뀔 때 대기 시간


    # 3. 데이터 중복 제거 및 엑셀 저장
    if all_articles:
        df = pd.DataFrame(all_articles)
        df = df.drop_duplicates(subset=["매물번호"])
        
        today = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"강서구_지식산업센터_매물_{today}.xlsx"
        
        df.to_excel(file_name, index=False)
        print(f"\n✅ 총 {len(df)}건의 매물이 엑셀 파일로 저장되었습니다: {file_name}")
    else:
        print("\n❌ 수집된 매물이 없습니다. 해당 조건의 매물이 없거나 API 상태를 확인해주세요.")

if __name__ == "__main__":
    crawling_naver_real_estate()
