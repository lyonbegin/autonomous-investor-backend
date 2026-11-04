"""JAX/XLA kernels used by GENERATED WF04 TPU screening programs.

Input for every primitive: [number_of_symbols, time_bars] float32.
Rolling indicators warm-up with NaN. EMA/RSI/MFI here are screening
approximations until independently verified against the exact converted Pine
code; no financial trades or source parity is asserted.

Cloud TPU: pip install 'jax[tpu]' on Google's TPU VM, not on Railway.
"""
from __future__ import annotations

import jax
import jax.numpy as jnp
from jax import lax


def _rolling(x, period, reducer, initial):
    if x.ndim != 2 or period < 2:
        raise ValueError("WF04_ROLLING_EXPECTS_2D_SERIES_AND_PERIOD")
    y=lax.reduce_window(x,initial,reducer,(1,period),(1,1),"VALID")
    return jnp.pad(y,((0,0),(period-1,0)),constant_values=jnp.nan)


def rolling_max(x,period):
    return _rolling(x,period,lax.max,-jnp.inf)


def rolling_min(x,period):
    return _rolling(x,period,lax.min,jnp.inf)


def _sum(x,period):
    return _rolling(x,period,lax.add,0.0)


def sma(x,period):
    return _sum(x,period)/period


def ema(x,period):
    """Screener EMA uses first input as its seed; source parity is REQUIRED."""
    alpha=2.0/(period+1.0)
    def series(row):
        def step(c,v):
            nxt=alpha*v+(1-alpha)*c
            return nxt,nxt
        _,rest=lax.scan(step,row[0],row[1:])
        return jnp.concatenate((row[:1],rest),axis=0)
    return jax.vmap(series)(x)


def rsi(x,period):
    delta=jnp.concatenate((jnp.zeros_like(x[:,:1]),x[:,1:]-x[:,:-1]),axis=1)
    positive=jnp.maximum(delta,0.0)
    negative=jnp.maximum(-delta,0.0)
    up=_sum(positive,period)
    down=_sum(negative,period)
    return jnp.where((down==0)&(up>0),100.0,
           jnp.where((down==0)&(up==0),50.0,100.0*up/(up+down)))


def mfi(high,low,close,volume,period):
    tp=(high+low+close)/3.0
    delta=tp[:,1:]-tp[:,:-1]
    pos=jnp.concatenate((jnp.zeros_like(tp[:,:1]),jnp.where(delta>0,tp[:,1:]*volume[:,1:],0.0)),axis=1)
    neg=jnp.concatenate((jnp.zeros_like(tp[:,:1]),jnp.where(delta<0,tp[:,1:]*volume[:,1:],0.0)),axis=1)
    p=_sum(pos,period)
    n=_sum(neg,period)
    return jnp.where((n==0)&(p>0),100.0,
           jnp.where((n==0)&(p==0),50.0,100.0*p/(p+n)))


def atr(high,low,close,period):
    prev=jnp.concatenate((close[:,:1],close[:,:-1]),axis=1)
    tr=jnp.maximum(high-low,jnp.maximum(jnp.abs(high-prev),jnp.abs(low-prev)))
    return sma(tr,period)
