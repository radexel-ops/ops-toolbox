// 1. 웹 앱 접속 시 HTML을 보여주는 함수
function doGet() {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('WEHAGO 폼 생성기')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

// 2. 스프레드시트에서 거래처 정보 가져오기 (비밀 데이터)
function getVendorData() {
  // 사용자가 제공한 스프레드시트 ID (절대 외부 유출 금지)
  const sheetId = '1oiw3gIYdidEnmxBL58W2oMMGsRhswa1CpG7mn88DKn0';
  const ss = SpreadsheetApp.openById(sheetId);
  const sheet = ss.getSheetByName('Vendors');

  // 시트가 없거나 에러 발생 시 빈 객체 반환
  if (!sheet) return {};

  const data = sheet.getDataRange().getValues();

  // 첫 줄(헤더) 제거하고 객체로 변환
  const vendors = {};
  for (let i = 1; i < data.length; i++) {
    // A열: 거래처명, B열: 계좌정보
    // 빈 줄이 아닌 경우에만 저장
    if(data[i][0]) {
       vendors[data[i][0]] = { account: data[i][1] };
    }
  }
  return vendors;
}

// 3. 스프레드시트에서 API 키 가져오기 (보안 적용)
function getApiKey() {
  const sheetId = '1oiw3gIYdidEnmxBL58W2oMMGsRhswa1CpG7mn88DKn0';
  const ss = SpreadsheetApp.openById(sheetId);
  const sheet = ss.getSheetByName('GEMINI_API_KEY');

  // 시트가 없으면 빈 값 반환
  if (!sheet) return '';

  // A1 셀에 키가 있다고 가정하고 가져옴 (헤더 없이 바로 키만 입력되어 있거나, A2에 있다면 A2로 수정 필요)
  // 여기서는 'A1'에 키 값이 들어있다고 가정합니다.
  const key = sheet.getRange('A1').getValue();
  return key;
}

// 4. 과거 이력 데이터 (서버에 안전하게 보관)
function getHistoryData() {
  // 기존 HTML 소스코드에 노출되어 있던 데이터를 서버 내부로 옮겼습니다.
  return [
    { category: "하드웨어 제작", vendor: "경기FA", itemName: "하드웨어_머시닝센터 제작 건", purpose: "하드웨어_머시닝센터 제작", account: "기업은행 471-036753-01-026", paymentMethod: "이체(KARA)" },
    { category: "하드웨어 제작", vendor: "121-87-02591", itemName: "Blade_로봇부_하드웨어_알루미늄용접물 제작 건", purpose: "Blade_로봇부_하드웨어_알루미늄용접물 제작", account: "기업은행 920-049581-04-019", paymentMethod: "이체(운영비)" },
    { category: "자문료", vendor: "서울아산병원 박기홍 박사", itemName: "레퍼런스 빔 데이터에 대한 dicom 분석 용역자문 실시", purpose: "아산병원 빔데이터 최신 알고리즘에 대한 MC simulation 분석 실시", account: "신한은행 / 254-910471-70707 / 예금주 : 박기홍", paymentMethod: "이체(데이터3차)" },
    { category: "수리", vendor: "컴마스터", itemName: "업무용 데스크탑 수리", purpose: "업무 중 장비를 이동·정리하는 과정에서 업무용 데스크탑에 물이 유입되어 고장이 발생해 수리 필요", account: "농협은행 / 517013-51-021555 / 예금주 : 임태환", note: "세금계산서 발행 불가능하므로, 사업자 현금영수증으로 대체" },
    { category: "부품구매", vendor: "동아MCT", itemName: "자동형head mag용 하드웨어 제작 건", purpose: "자동형 head mag 하드웨어 제작", account: "IM뱅크 156-08-010722-1 (예금주:동아MCT)", paymentMethod: "계좌이체" },
    { category: "부품구매", vendor: "이구스", itemName: "자동형 head mag용 레일 구매 건", purpose: "자동형 head mag구동부 레일 2차 장착", account: "하나은행 404-890002-31004 (예금주:한국이구스)" },
    { category: "시편제작", vendor: "메트로테크", itemName: "SECC 0.5 T 15 X 100 mm", purpose: "MPRT-CM Elekta 장비 부착물의 자력 테스트를 위한 자성체 시편 제작", account: "IBK기업은행 / 415-022977-01-016 / 예금주 : (주)메트로테크안양공장" },
    { category: "외주용역", vendor: "셀라", itemName: "EMC 디버깅(ESD) 외주 용역", purpose: "EMC ESD 시험 디버깅을 위한 전문가 필요", account: "신한은행 / 110-295-060151 / 예금주 : 김나영" },
    { category: "인증시험", vendor: "넴코코리아", itemName: "EMC Lab Shieldroom 입회 시험(추가 시험)", purpose: "전자파 적합성 시험 중 Shieldroom 시험 추가 진행", account: "우리은행 / 398-092798-13-101 / 예금주 : 주식회사넴코코리아" },
    { category: "시험비용", vendor: "스탠다드랩", itemName: "Non-GLP 세포독성 테스트", purpose: "MPRT-BA 세포독성 시험 불합격으로 인한 non-GLP 테스트 진행", account: "하나은행 / 476-910028-45704 / 예금주 : 주식회사 스탠다드랩" },
    { category: "특허", vendor: "특허법인 비엘티", itemName: "BPP2021-0030AUD1 등록료 송금", purpose: "호주특허 등록료 송금", account: "우리은행 / 1005303954125 / 예금주: 특허법인 비엘티" },
    { category: "교육", vendor: "인프런", itemName: "김영한의 실전자바 - 기본편", purpose: "객체지향에 대한 이해 필요 코드 재사용성, 확장성, 모듈화, 추상화, 유지보수 등을 위한 프로그래밍 필요", paymentMethod: "개인법인카드" },
    { category: "교육", vendor: "(주) 가우스텍", itemName: "오페라 영구자석 해석 관련 교육", purpose: "MPRT-HM 및 MPRT-CM에 필요한 영구자석 설계 및 해석을 위한 교육", account: "신한은행 / 140-007-088210 / 예금주 : (주) 가우스텍" }
  ];
}