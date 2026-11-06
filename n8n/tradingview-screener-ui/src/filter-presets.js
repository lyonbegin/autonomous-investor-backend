// Verified quick-selection labels and bounds from 2026-11-06 Playwright original
// popup observations (menu_snapshots.json); unavailable technical crossovers are not fabricated.
const gt=(label,value,description='')=>({label,description,operation:'greater',min:String(value),max:''});
const gte=(label,value,description='')=>({label,description,operation:'egreater',min:String(value),max:''});
const lt=(label,value,description='')=>({label,description,operation:'less',min:String(value),max:''});
const lte=(label,value,description='')=>({label,description,operation:'eless',min:String(value),max:''});
const eq=(label,value,description='')=>({label,description,operation:'equal',min:String(value),max:''});
const range=(label,min,max,description='')=>({label,description,operation:'in_range',min:String(min),max:String(max)});
const gains=[
 gt('초과 30%',30,'예외적 상승'),gt('초과 20%',20,'매우 강한 상승'),
 gt('초과 10%',10,'강한 상승'),gt('초과 5%',5,'보통 상승'),
 range('0% ~ 5%',0,5,'약한 상승'),gt('초과 0%',0,'상승'),
 lt('미만 0%',0,'하락'),range('−5% ~ 0%',-5,0,'약한 하락'),
 lt('미만 −5%',-5,'보통 하락'),lt('미만 −10%',-10,'강한 하락'),
 lt('미만 −20%',-20,'심각한 하락'),lt('미만 −30%',-30)
];
const growth=[
 gt('초과 50%',50,'탁월한 성장'),range('25% ~ 50%',25,50,'강한 성장'),
 range('10% ~ 25%',10,25,'보통 성장'),range('5% ~ 10%',5,10,'낮은 성장'),
 range('0% ~ 5%',0,5,'최소한의 성장'),gt('초과 0%',0,'성장'),
 lt('미만 0%',0,'감소'),range('−25% ~ 0%',-25,0,'보통 감소'),
 range('−50% ~ −25%',-50,-25,'강한 감소'),lt('미만 −50%',-50,'심각한 감소')
];
const dividends=[
 gt('초과 15%',15,'탁월함'),range('10% ~ 15%',10,15,'매우 높음'),
 range('6% ~ 10%',6,10,'높음'),range('4% ~ 6%',4,6,'보통'),
 range('2% ~ 4%',2,4,'낮음'),range('0% ~ 2%',0,2,'매우 낮음'),
 eq('0%',0,'배당 없음')
];
const common={
 '체인지 %':gains,'퍼포먼스 %':gains
};
const stock={
 ...common,
 '가격':[gt('초과 100',100),range('10 ~ 100',10,100,'중간 가격대'),lte('10 및 그 아래',10),lte('5 및 그 아래',5,'동전주')],
 '시가총액':[gte('200 B 및 그 위',200e9,'메가'),range('10 B ~ 200 B',10e9,200e9,'큼'),range('2 B ~ 10 B',2e9,10e9,'미드'),range('300 M ~ 2 B',300e6,2e9,'작음'),range('50 M ~ 300 M',50e6,300e6,'마이크로'),lte('50 M 및 그 아래',50e6,'나노')],
 'P/E':[gte('50 및 그 위',50,'극도로 높음'),range('35 ~ 50',35,50,'매우 높음'),range('25 ~ 35',25,35,'높음'),range('15 ~ 25',15,25,'보통'),range('5 ~ 15',5,15,'낮음'),range('0 ~ 5',0,5,'매우 낮음')],
 'EPS 희석 성장':growth,
 '매출 성장률':growth,
 '배당 수익 %':dividends,
 'PEG':[gt('초과 3',3,'극도로 높음'),range('2 ~ 3',2,3,'매우 높음'),range('1.5 ~ 2',1.5,2,'높음'),range('1 ~ 1.5',1,1.5,'보통'),range('0.5 ~ 1',0.5,1,'낮음'),range('0 ~ 0.5',0,0.5,'매우 낮음'),lt('미만 0',0,'네거티브')],
 'ROE':[gt('초과 30%',30,'매우 높음'),range('20% ~ 30%',20,30,'높음'),range('10% ~ 20%',10,20,'보통'),range('5% ~ 10%',5,10,'낮음'),range('0% ~ 5%',0,5,'매우 낮음'),gt('초과 0%',0,'포지티브'),lte('0% 및 그 아래',0,'제로 및 마이너스'),range('−15% ~ 0%',-15,0,'보통 손실'),range('−30% ~ −15%',-30,-15,'막대한 손실'),lt('미만 −30%',-30)],
 '베타':[gt('초과 1.5',1.5,'매우 높은 변동성'),range('1.1 ~ 1.5',1.1,1.5,'높은 변동성'),range('0.9 ~ 1.1',0.9,1.1,'시장 변동성 근접'),range('0.5 ~ 0.9',0.5,0.9,'저변동성'),range('0 ~ 0.5',0,.5,'매우 낮은 변동성'),gt('초과 0',0,'양의 민감도'),lt('미만 0',0,'역민감도')]
};
const etf={
 ...common,
 'NAV 총 수익률':gains,
 'AUM':[gte('10 B 및 그 위',10e9,'메가'),range('1 B ~ 10 B',1e9,10e9,'큼'),range('500 M ~ 1 B',500e6,1e9,'미드'),range('100 M ~ 500 M',100e6,500e6,'작음'),range('50 M ~ 100 M',50e6,100e6,'마이크로'),lte('50 M 및 그 아래',50e6,'나노')],
 '배당 수익률 % (표시됨)':dividends,
 '지출 비율':[gte('1% 및 그 위',1,'극도로 높음'),range('0.75% ~ 1%',.75,1,'매우 높음'),range('0.5% ~ 0.75%',.5,.75,'높음'),range('0.2% ~ 0.5%',.2,.5,'보통'),range('0.1% ~ 0.2%',.1,.2,'낮음'),lte('0.1% 및 그 아래',.1,'매우 낮음')]
};
const bond={
 '쿠폰 %':[gt('초과 15%',15,'탁월함'),range('10% ~ 15%',10,15,'매우 높음'),range('6% ~ 9%',6,9,'높음'),range('4% ~ 6%',4,6,'보통'),range('2% ~ 4%',2,4,'낮음'),range('0% ~ 2%',0,2,'매우 낮음'),eq('0%',0,'무이표')]
};
export function getPresets(product,label){return ({stock,etf,bond})[product]?.[label]||[]}
