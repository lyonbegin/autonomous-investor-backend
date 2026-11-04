from datetime import date, timedelta
import sqlite3
from market_daily_10y.collector import Instrument, Store, ten_year_window
from market_daily_10y.scheduler import CollectionQueue


def instruments(n=6):
    return [Instrument('equity','NASDAQ',f'X{i:02}',f'X{i:02}','America/New_York') for i in range(n)]


def test_stable_queue_no_offset_skips_when_universe_changes(tmp_path):
    store = Store(tmp_path)
    q = CollectionQueue(store)
    asof = date(2026,11,5)
    listed = instruments(5)
    q.seed(listed, asof)
    first = q.choose(listed,asof,2)
    assert [x.symbol for x in first] == ['X00','X01']
    for inst in first:
        q.record(inst,asof,{'status':'COLLECTED','eligible':True,'rows':2500})
    # Add new name before all existing names; prior selections remain recorded.
    new = Instrument('equity','NASDAQ','A_NEW','A_NEW','America/New_York')
    q.seed([new]+listed,asof+timedelta(days=1))
    second = q.choose([new]+listed,asof+timedelta(days=1),4)
    assert not {'X00','X01'}.intersection(x.symbol for x in second)
    assert {'X02','X03','X04','A_NEW'} == {x.symbol for x in second}


def test_retry_backoff_and_no_success_claim(tmp_path):
    store=Store(tmp_path)
    q=CollectionQueue(store)
    asof=date(2026,11,5)
    listed=instruments(2)
    q.seed(listed,asof)
    q.record(listed[0],asof,{'status':'FAILED','reason':'HTTP 429'})
    chosen=q.choose(listed,asof+timedelta(days=1),5)
    assert [x.key for x in chosen]==[listed[1].key]
    chosen=q.choose(listed,asof+timedelta(days=2),5)
    assert listed[0].key in [x.key for x in chosen]
    assert q.report(asof)['result_counts']['FAILED']==1


def test_refresh_quota_does_not_starve_initial_import(tmp_path):
    store=Store(tmp_path)
    q=CollectionQueue(store)
    d=date(2026,11,5)
    listed=instruments(10)
    q.seed(listed,d)
    for inst in listed[:4]:
        q.record(inst,d,{'status':'COLLECTED','eligible':True,'rows':2500})
    later=d+timedelta(days=8)
    chosen=q.choose(listed,later,4,refresh_fraction=0.25)
    assert chosen[0].key==listed[0].key
    assert {x.key for x in chosen[1:]}=={x.key for x in listed[4:7]}
    # The pool cannot provide seven-day freshness to all instruments at tiny capacity.
    progress=q.report(later,batch_limit=1)
    assert progress['capacity_below_7d_full_refresh']
    assert progress['minimum_daily_capacity_for_7d_refresh']==2


def test_ineligible_history_scheduled_not_exposed_as_eligible(tmp_path):
    store=Store(tmp_path)
    q=CollectionQueue(store)
    d=date(2026,11,5)
    inst=instruments(1)[0]
    q.seed([inst],d)
    due=q.record(inst,d,{'status':'COLLECTED','eligible':False,'rows':90})
    assert due=='2026-12-05'
    assert q.choose([inst],d+timedelta(days=8),5)==[]
    assert q.report(d)['result_counts']['COLLECTED_INELIGIBLE']==1


def test_migrate_previous_catalog_without_redownloading_immediately(tmp_path):
    store=Store(tmp_path)
    inst=instruments(1)[0]
    d=date(2026,11,5)
    start,end=ten_year_window(d)
    with sqlite3.connect(store.db) as con:
        con.execute("""INSERT INTO instruments
          (key,asset_class,exchange,symbol,vendor_symbol,timezone,calendar,
           contract_type,start,end_exclusive,first_date,last_date,rows,coverage,
           eligible,reasons,sha256,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (inst.key,'equity','NASDAQ',inst.symbol,inst.vendor_symbol,
           inst.timezone,'weekday','spot',str(start),str(end),
           str(start),'2026-11-04',2500,.96,1,'[]','abc','2026-11-05T00:00:00Z'))
    queue=CollectionQueue(store)
    queue.seed([inst],d)
    assert queue.choose([inst],d,3)==[]
    assert queue.report(d)['recent_eligible_rows']==1


def test_balanced_intake_across_exchanges(tmp_path):
    store=Store(tmp_path)
    q=CollectionQueue(store)
    now=date(2026,11,5)
    nas=instruments(30)
    hk=[Instrument('equity','HKEX',f'{i:04}',f'{i:04}.HK','Asia/Hong_Kong')
        for i in range(15)]
    q.seed(nas+hk,now)
    selected=q.choose(nas+hk,now,12)
    assert sum(x.exchange=='HKEX' for x in selected)==6
    assert sum(x.exchange=='NASDAQ' for x in selected)==6
    for inst in selected:q.record(inst,now,{'status':'COLLECTED','eligible':True,'rows':2400})
    again=q.choose(nas+hk,now,12)
    assert {i.key for i in selected}.isdisjoint({i.key for i in again})

