import io
from datetime import date,timedelta

import numpy as np
import pandas as pd
import pytest

from market_daily_10y.collector import Instrument, Store, ten_year_window
from market_daily_10y.s3_bridge import PrivatePoolBridge

ASOF=date(2026,11,4)
START,END=ten_year_window(ASOF)
A=Instrument('equity','NASDAQ','AAPL','AAPL','America/New_York')
B=Instrument('equity','TSE','7203','7203.T','Asia/Tokyo')


class FakePrivateS3:
    def __init__(self):
        self.objects={}
    def put_object(self,Bucket,Key,Body,**kwargs):
        self.objects[(Bucket,Key)]=bytes(Body)
    def get_object(self,Bucket,Key):
        return {'Body':io.BytesIO(self.objects[(Bucket,Key)])}


def bars(multiplier=1):
    d=pd.date_range(START,END-timedelta(days=1),freq='B')
    rng=np.random.default_rng(111)
    close=multiplier*100*np.exp(np.cumsum(rng.normal(.001,.01,len(d))))
    return pd.DataFrame({'date':d,'open':close,'high':close*1.01,
                         'low':close*.99,'close':close,'volume':1000})


def build(tmp_path):
    publisher=Store(tmp_path/'publisher')
    publisher.save(A,bars(),START,END)
    publisher.save(B,bars(2),START,END)
    s3=FakePrivateS3()
    bridge=PrivatePoolBridge(publisher,s3,'private-research')
    return publisher,s3,bridge


def test_private_immutable_s3_mirror_and_hydrate_exact_original_bytes(tmp_path):
    _,s3,bridge=build(tmp_path)
    x=bridge.mirror_instrument(A)
    bridge.mirror_instrument(B)
    assert x['status']=='MIRRORED'
    assert bridge.mirror_instrument(A)['status']=='ALREADY_MIRRORED'
    report=bridge.publish(ASOF)
    assert report['ready']==2
    assert report['manifest_sha256']
    received=bridge.hydrate(ASOF,[A.key,B.key],tmp_path/'consumer')
    assert received['rechecked']==2
    restored=Store(tmp_path/'consumer')
    assert restored.status()['eligible']==2
    assert restored.read(A)['close'].equals(bridge.store.read(A)['close'])
    assert restored.file(A).read_bytes()==bridge.store.file(A).read_bytes()
    assert not any('http://' in str(v) for v in s3.objects.values())


def test_corrupt_remote_parquet_is_rejected_not_silent(tmp_path):
    _,s3,bridge=build(tmp_path)
    a=bridge.mirror_instrument(A)
    bridge.mirror_instrument(B)
    bridge.publish(ASOF)
    s3.objects[('private-research',a['key'])]+=b'INVALID'
    with pytest.raises(ValueError,match='S3_PARQUET_HASH_MISMATCH'):
        bridge.hydrate(ASOF,[A.key],tmp_path/'corrupted')


def test_stale_s3_mirror_does_not_publish_latest_local_revision(tmp_path):
    store,s3,bridge=build(tmp_path)
    bridge.mirror_instrument(A)
    bridge.mirror_instrument(B)
    # A has new local version, old S3 SHA can no longer be exposed as current.
    newer=bars()
    newer.loc[0,'close']*=1.001
    newer.loc[0,'high']=max(newer.loc[0,'high'],newer.loc[0,'close'])
    store.save(A,newer,START,END)
    report=bridge.publish(ASOF)
    assert report['ready']==1
    with pytest.raises(ValueError,match='S3_UNVERIFIED_INSTRUMENT'):
        bridge.hydrate(ASOF,[A.key],tmp_path/'stale')


def test_missing_selection_and_snapshot_not_trusted(tmp_path):
    _,s3,bridge=build(tmp_path)
    bridge.mirror_instrument(A)
    bridge.publish(ASOF)
    with pytest.raises(KeyError):
        bridge.hydrate(ASOF+timedelta(days=1),[A.key],tmp_path/'bad')
    with pytest.raises(ValueError,match='S3_UNVERIFIED_INSTRUMENT'):
        bridge.hydrate(ASOF,[B.key],tmp_path/'not-sent')


def test_collector_cli_opt_in_s3_mirror_writes_remote_manifest(tmp_path,monkeypatch,capsys):
    import json
    import market_daily_10y.collector as collector
    import market_daily_10y.s3_bridge as transport
    fake=FakePrivateS3()
    monkeypatch.setattr(transport,'s3_client_from_env',
                        lambda:(fake,'private-research'))
    def local_fetch(store,inst,start,end):
        q=store.save(inst,bars(),start,end)
        return {'status':'COLLECTED',**q}
    monkeypatch.setattr(collector,'sync',local_fetch)
    csv_path=tmp_path/'one.csv'
    csv_path.write_text('asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n'
                        'equity,NASDAQ,AAPL,AAPL,America/New_York,weekday,spot\n')
    collector.main(['--root',str(tmp_path/'actual'),'--universe',str(csv_path),
                    '--asof','2026-11-04','--queue','--mirror-s3',
                    '--limit','1','--pause','0'])
    summary=json.loads(capsys.readouterr().out.splitlines()[-1])
    assert summary['attempted']==1
    assert summary['s3_mirror_failed']==0
    assert summary['s3_manifest']['status']=='PUBLISHED_PRIVATE_MANIFEST'
    assert summary['s3_manifest']['ready']==1
    assert len(fake.objects)==3


def test_remote_outage_recorded_but_local_parquet_is_preserved(tmp_path,monkeypatch,capsys):
    import json
    import market_daily_10y.collector as collector
    import market_daily_10y.s3_bridge as transport
    class BrokenS3(FakePrivateS3):
        def put_object(self,**kwargs):
            raise ConnectionError('S3_NOT_REACHABLE')
    fake=BrokenS3()
    monkeypatch.setattr(transport,'s3_client_from_env',
                        lambda:(fake,'private-research'))
    def local_fetch(store,inst,start,end):
        q=store.save(inst,bars(),start,end)
        return {'status':'COLLECTED',**q}
    monkeypatch.setattr(collector,'sync',local_fetch)
    csv_path=tmp_path/'one.csv'
    csv_path.write_text('asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n'
                        'equity,NASDAQ,AAPL,AAPL,America/New_York,weekday,spot\n')
    root=tmp_path/'actual'
    collector.main(['--root',str(root),'--universe',str(csv_path),
                    '--asof','2026-11-04','--mirror-s3',
                    '--limit','1','--pause','0'])
    output=capsys.readouterr().out.splitlines()
    summary=json.loads(output[-1])
    assert summary['s3_mirror_failed']==1
    assert summary['s3_manifest']['status']=='NOT_PUBLISHED'
    assert Store(root).status()['eligible']==1
