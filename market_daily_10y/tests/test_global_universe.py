import csv
import json
import pandas as pd
import pytest
from market_daily_10y.global_universe import parse_snapshot, merge_snapshots


def test_jpx_header_discovery_and_quarantine(tmp_path):
    path = tmp_path / 'jpx.xlsx'
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([
            ['JPX Listing Master', None, None],
            ['コード','市場・商品区分','銘柄名'],
            ['7203','プライム（内国株式）','TOYOTA'],
            ['1306','ETF','ETF'],
            ['130A','グロース（内国株式）','NEW'],
            ['9001','不動産投資信託','REIT'],
        ]).to_excel(writer,index=False,header=False)
    accepted,rejected=parse_snapshot(path,'jpx')
    assert [x['vendor_symbol'] for x in accepted]==['7203.T','1306.T']
    assert rejected[0]['reason']=='JPX_COMPLEX_OR_NEW_CODE'
    assert len(rejected)==2


def test_hkex_equity_etf_and_cbbc_exclusion(tmp_path):
    p=tmp_path/'hkex.xlsx'
    pd.DataFrame({'Stock Code':['00001','700','02800','12345'],
       'Category':['Equity Securities','Equity Securities','Exchange Traded Products','Derivative Warrants'],
       'Sub-Category':['Ordinary Shares','Ordinary Shares','ETF','Call Warrant']}).to_excel(p,index=False)
    accepted,rejected=parse_snapshot(p,'hkex')
    assert [r['vendor_symbol'] for r in accepted] == ['0001.HK','0700.HK','2800.HK']
    assert len(rejected)==1


def test_krx_mapping_and_preserve_leading_zeros(tmp_path):
    p=tmp_path/'krx.csv'
    p.write_text('단축코드,시장구분\n005930,KOSPI\n035720,KOSDAQ\n123456,KONEX\n',encoding='utf-8')
    accepted,rejected=parse_snapshot(p,'krx')
    assert [r['vendor_symbol'] for r in accepted]==['005930.KS','035720.KQ']
    assert rejected[0]['reason']=='KRX_MARKET_OR_INSTRUMENT_UNMAPPED'


def test_merge_preserves_base_and_does_not_mark_price_as_collected(tmp_path):
    base=tmp_path/'base.csv'
    base.write_text('asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n'
        'equity,TSE,7203,7203.T,Asia/Tokyo,weekday,spot\n'
        'crypto_spot,GLOBAL,BTCUSD,BTC-USD,UTC,seven_day,spot\n',encoding='utf-8')
    p=tmp_path/'krx.csv'
    p.write_text('단축코드,시장구분\n005930,KOSPI\n',encoding='utf-8')
    out,meta,rejected=[tmp_path/x for x in ('out.csv','report.json','rejected.json')]
    report=merge_snapshots(base,{'krx':p},out,meta,rejected)
    assert report['total_universe']==3
    assert not report['price_history_fetched']
    assert report['sources']['krx']['added']==1
    assert len(list(csv.DictReader(out.open())))==3
    assert json.loads(meta.read_text())['output_sha256']==report['output_sha256']


def test_corrupt_snapshot_does_not_write_output(tmp_path):
    base=tmp_path/'base.csv'
    base.write_text('asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n',encoding='utf-8')
    bad=tmp_path/'bad.csv'
    bad.write_text('wrong,columns\nx,y\n')
    out=tmp_path/'out.csv'
    with pytest.raises(ValueError):
        merge_snapshots(base,{'jpx':bad},out,tmp_path/'meta.json')
    assert not out.exists()
