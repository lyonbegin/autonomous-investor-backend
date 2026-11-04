import io
import pandas as pd
import pytest
from market_daily_10y.world_bootstrap import prepare_global_universe


def fake_hkex(url):
    buf = io.BytesIO()
    pd.DataFrame({'Stock Code':['00700','00200'],
                  'Category':['Equity Securities']*2,
                  'Sub-Category':['Ordinary Shares']*2}).to_excel(buf,index=False)
    return buf.getvalue()


def fake_us(url):
    if 'nasdaqlisted' in url:
        return ('Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n'
                'AAPL|Apple|Q|N|N|100|N|N\n')
    return ('ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n'
            'IBM|IBM|N|IBM|N|100|N|IBM\n')


def test_bootstrap_and_cached_offline_reuse(tmp_path):
    base=tmp_path/'base.csv'
    base.write_text('asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n'
                    'crypto_spot,GLOBAL,BTCUSD,BTC-USD,UTC,seven_day,spot\n')
    out,details=prepare_global_universe(tmp_path,base,allow_network=True,
         us_fetch=fake_us,hkex_fetch=fake_hkex,min_us=1,min_hkex=1)
    assert details['hkex_accepted']==2
    assert details['world_universe_count']==5
    assert not details['full_worldwide_universe']
    def cannot_fetch(_):
        raise AssertionError('should not call internet when source snapshot fresh')
    out2,details2=prepare_global_universe(tmp_path,base,allow_network=False,
         us_fetch=cannot_fetch,hkex_fetch=cannot_fetch,min_us=1,min_hkex=1)
    assert out2 == out
    assert details2['world_universe_count']==5


def test_missing_source_never_claims_global_ready(tmp_path):
    base=tmp_path/'base.csv'
    base.write_text('asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n')
    with pytest.raises(ValueError, match='OFFICIAL_US_SOURCE_NOT_READY'):
        prepare_global_universe(tmp_path,base,allow_network=False)


def test_failed_remote_update_reuses_old_valid_master(tmp_path):
    base=tmp_path/'base.csv'
    base.write_text('asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n')
    prepare_global_universe(tmp_path,base,allow_network=True,
         us_fetch=fake_us,hkex_fetch=fake_hkex,min_us=1,min_hkex=1)
    def broken(_):raise ConnectionError('official host unavailable')
    _,evidence=prepare_global_universe(tmp_path,base,allow_network=True,
         us_fetch=broken,hkex_fetch=broken,min_us=1,min_hkex=1,max_age_days=0)
    assert set(evidence['source_stale'])=={'nasdaq','other','hkex'}
    assert 'source_errors' in evidence
