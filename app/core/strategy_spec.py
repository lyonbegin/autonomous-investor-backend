from __future__ import annotations

import ast
import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any


SUPPORTED_TA = {
    "sma", "ema", "rsi", "atr", "highest", "lowest",
    "crossover", "crossunder", "change",
}


class StrategySpecError(ValueError):
    pass


def _clean_source(source: str) -> str:
    lines: list[str] = []
    for raw in str(source or "").replace("\r\n", "\n").split("\n"):
        line = raw.split("//", 1)[0].rstrip()
        if line.strip():
            lines.append(line)
    return "\n".join(lines)


def _input_value(expr: str) -> float | int | bool | str | None:
    match = re.match(r"input\.(?:int|float|bool|string)\s*\((.*)\)\s*$", expr.strip())
    if not match:
        return None
    body = match.group(1)
    named = re.search(r"(?:defval\s*=\s*)?([-+]?\d+(?:\.\d+)?)", body)
    if named:
        raw = named.group(1)
        return float(raw) if "." in raw else int(raw)
    if re.search(r"\btrue\b", body, re.I):
        return True
    if re.search(r"\bfalse\b", body, re.I):
        return False
    quoted = re.search(r'["\']([^"\']+)["\']', body)
    return quoted.group(1) if quoted else None


def _normalize_expr(expr: str) -> str:
    value = expr.strip().rstrip(";")
    value = re.sub(r"\btrue\b", "True", value, flags=re.I)
    value = re.sub(r"\bfalse\b", "False", value, flags=re.I)
    value = re.sub(r"\bna\b", "float('nan')", value)
    return value


def _condition_for_call(lines: list[str], index: int, call_text: str) -> str:
    when = re.search(r"\bwhen\s*=\s*([^,)]+(?:\([^)]*\))?[^,)]*)", call_text)
    if when:
        return when.group(1).strip()
    indent = len(lines[index]) - len(lines[index].lstrip())
    for j in range(index - 1, -1, -1):
        line = lines[j]
        stripped = line.strip()
        if not stripped:
            continue
        prev_indent = len(line) - len(line.lstrip())
        if prev_indent < indent and stripped.startswith("if "):
            return stripped[3:].strip()
        if prev_indent < indent:
            break
    return "True"


def compile_pine_to_spec(source_id: str, source: str) -> dict[str, Any]:
    clean = _clean_source(source)
    if not clean:
        raise StrategySpecError("empty Pine source")
    version_match = re.search(r"//@version\s*=\s*(\d+)", source)
    version = int(version_match.group(1)) if version_match else None
    if "strategy(" not in clean:
        raise StrategySpecError("Pine source is not a strategy() script")

    hard_unsupported = []
    for token, reason in [
        ("request.security", "multi-timeframe request.security"),
        ("strategy.exit", "strategy.exit stop/limit/trailing semantics"),
        ("strategy.order", "strategy.order advanced order semantics"),
        ("strategy.cancel", "strategy.cancel semantics"),
        ("varip ", "varip intrabar state"),
    ]:
        if token in clean:
            hard_unsupported.append(reason)
    if re.search(r"(^|\n)\s*[^\n]+\s*:=\s*", clean):
        hard_unsupported.append("stateful := assignment")
    if hard_unsupported:
        raise StrategySpecError("; ".join(sorted(set(hard_unsupported))))

    lines = clean.split("\n")
    constants: dict[str, Any] = {}
    expressions: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("if ", "for ", "while ", "switch ")):
            continue
        match = re.match(
            r"(?:var\s+)?(?:float|int|bool|string)?\s*([A-Za-z_]\w*)\s*=\s*(.+)$",
            stripped,
        )
        if not match:
            continue
        name, expr = match.group(1), match.group(2).strip()
        input_value = _input_value(expr)
        if input_value is not None:
            constants[name] = input_value
        elif not expr.startswith("strategy("):
            expressions[name] = _normalize_expr(expr)

    entries: list[dict[str, str]] = []
    closes: list[dict[str, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if "strategy.entry" in stripped:
            direction = "long" if "strategy.long" in stripped else ("short" if "strategy.short" in stripped else "")
            if not direction:
                raise StrategySpecError("strategy.entry without strategy.long/strategy.short")
            entries.append(
                {
                    "direction": direction,
                    "condition": _normalize_expr(_condition_for_call(lines, idx, stripped)),
                    "source_line": stripped,
                }
            )
        elif "strategy.close_all" in stripped:
            closes.append(
                {
                    "direction": "all",
                    "condition": _normalize_expr(_condition_for_call(lines, idx, stripped)),
                    "source_line": stripped,
                }
            )
        elif "strategy.close" in stripped:
            id_match = re.search(r"strategy\.close\s*\(\s*[\"\']([^\"\']+)", stripped)
            close_id = (id_match.group(1) if id_match else "").lower()
            direction = "short" if "short" in close_id else ("long" if "long" in close_id else "all")
            closes.append(
                {
                    "direction": direction,
                    "condition": _normalize_expr(_condition_for_call(lines, idx, stripped)),
                    "source_line": stripped,
                }
            )

    if not entries:
        raise StrategySpecError("no strategy.entry calls found")

    long_entries = [x["condition"] for x in entries if x["direction"] == "long"]
    short_entries = [x["condition"] for x in entries if x["direction"] == "short"]
    long_exits = [x["condition"] for x in closes if x["direction"] in {"long", "all"}]
    short_exits = [x["condition"] for x in closes if x["direction"] in {"short", "all"}]

    if not long_exits and short_entries:
        long_exits = list(short_entries)
    if not short_exits and long_entries:
        short_exits = list(long_entries)

    spec = {
        "spec_version": "StrategySpec-v1",
        "source_id": source_id,
        "pine_version": version,
        "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "constants": constants,
        "expressions": expressions,
        "entry_long": " or ".join(f"({x})" for x in long_entries) if long_entries else None,
        "entry_short": " or ".join(f"({x})" for x in short_entries) if short_entries else None,
        "exit_long": " or ".join(f"({x})" for x in long_exits) if long_exits else None,
        "exit_short": " or ".join(f"({x})" for x in short_exits) if short_exits else None,
        "order_model": "signal on bar close; fill on next bar open",
        "sizing_model": "normalized full-notional signal backtest",
        "supported_semantics": sorted(SUPPORTED_TA),
    }

    # Parse every expression now so unsupported syntax fails before a backtest.
    for expr in [
        *expressions.values(),
        spec["entry_long"],
        spec["entry_short"],
        spec["exit_long"],
        spec["exit_short"],
    ]:
        if expr:
            try:
                ast.parse(expr, mode="eval")
            except SyntaxError as exc:
                raise StrategySpecError(f"unsupported Pine expression: {expr[:160]}") from exc
    return spec


@dataclass
class _SeriesEngine:
    spec: dict[str, Any]
    bars: list[dict[str, Any]]

    def __post_init__(self) -> None:
        self.base = {
            "open": [float(x["open"]) for x in self.bars],
            "high": [float(x["high"]) for x in self.bars],
            "low": [float(x["low"]) for x in self.bars],
            "close": [float(x["close"]) for x in self.bars],
            "volume": [float(x.get("volume") or 0.0) for x in self.bars],
            "bar_index": [float(i) for i in range(len(self.bars))],
        }
        self.constants = dict(self.spec.get("constants") or {})
        self.definitions = dict(self.spec.get("expressions") or {})
        self.cache: dict[str, list[Any]] = {}

    def series_for_expr(self, expr: str | None) -> list[bool]:
        if not expr:
            return [False] * len(self.bars)
        node = ast.parse(expr, mode="eval").body
        return [bool(x) if not self._is_na(x) else False for x in self._series(node)]

    @staticmethod
    def _is_na(value: Any) -> bool:
        return isinstance(value, float) and math.isnan(value)

    def _length(self, node: ast.AST) -> int:
        values = self._series(node)
        for value in reversed(values):
            if not self._is_na(value):
                try:
                    return max(1, int(value))
                except (TypeError, ValueError):
                    break
        raise StrategySpecError("indicator length is not a constant numeric value")

    def _series(self, node: ast.AST) -> list[Any]:
        key = ast.dump(node, include_attributes=False)
        if key in self.cache:
            return self.cache[key]
        n = len(self.bars)

        if isinstance(node, ast.Constant):
            out = [node.value] * n
        elif isinstance(node, ast.Name):
            if node.id in self.base:
                out = self.base[node.id]
            elif node.id in self.constants:
                out = [self.constants[node.id]] * n
            elif node.id in self.definitions:
                out = self._series(ast.parse(self.definitions[node.id], mode="eval").body)
            elif node.id in {"True", "False"}:
                out = [node.id == "True"] * n
            else:
                raise StrategySpecError(f"unknown Pine identifier: {node.id}")
        elif isinstance(node, ast.Subscript):
            base = self._series(node.value)
            if isinstance(node.slice, ast.Constant):
                offset = int(node.slice.value)
            else:
                raise StrategySpecError("only constant history offsets like x[1] are supported")
            out = [float("nan") if i - offset < 0 else base[i - offset] for i in range(n)]
        elif isinstance(node, ast.UnaryOp):
            values = self._series(node.operand)
            if isinstance(node.op, ast.Not):
                out = [not bool(x) for x in values]
            elif isinstance(node.op, ast.USub):
                out = [-float(x) if not self._is_na(x) else x for x in values]
            elif isinstance(node.op, ast.UAdd):
                out = [float(x) if not self._is_na(x) else x for x in values]
            else:
                raise StrategySpecError("unsupported unary operator")
        elif isinstance(node, ast.BinOp):
            left, right = self._series(node.left), self._series(node.right)
            def calc(a: Any, b: Any) -> Any:
                if self._is_na(a) or self._is_na(b):
                    return float("nan")
                if isinstance(node.op, ast.Add): return float(a) + float(b)
                if isinstance(node.op, ast.Sub): return float(a) - float(b)
                if isinstance(node.op, ast.Mult): return float(a) * float(b)
                if isinstance(node.op, ast.Div): return float(a) / float(b) if float(b) != 0 else float("nan")
                if isinstance(node.op, ast.Mod): return float(a) % float(b) if float(b) != 0 else float("nan")
                raise StrategySpecError("unsupported arithmetic operator")
            out = [calc(a, b) for a, b in zip(left, right)]
        elif isinstance(node, ast.BoolOp):
            parts = [self._series(x) for x in node.values]
            if isinstance(node.op, ast.And):
                out = [all(bool(p[i]) for p in parts) for i in range(n)]
            elif isinstance(node.op, ast.Or):
                out = [any(bool(p[i]) for p in parts) for i in range(n)]
            else:
                raise StrategySpecError("unsupported boolean operator")
        elif isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise StrategySpecError("chained comparisons are not supported")
            left, right = self._series(node.left), self._series(node.comparators[0])
            op = node.ops[0]
            def cmp(a: Any, b: Any) -> bool:
                if self._is_na(a) or self._is_na(b): return False
                if isinstance(op, ast.Gt): return a > b
                if isinstance(op, ast.GtE): return a >= b
                if isinstance(op, ast.Lt): return a < b
                if isinstance(op, ast.LtE): return a <= b
                if isinstance(op, ast.Eq): return a == b
                if isinstance(op, ast.NotEq): return a != b
                raise StrategySpecError("unsupported comparison")
            out = [cmp(a, b) for a, b in zip(left, right)]
        elif isinstance(node, ast.Call):
            out = self._call(node)
        else:
            raise StrategySpecError(f"unsupported expression node: {type(node).__name__}")

        self.cache[key] = out
        return out

    def _call(self, node: ast.Call) -> list[Any]:
        n = len(self.bars)
        name = ""
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            name = f"{node.func.value.id}.{node.func.attr}"
        elif isinstance(node.func, ast.Name):
            name = node.func.id

        if name == "float":
            return [float("nan")] * n
        if name in {"abs", "math.abs"}:
            values = self._series(node.args[0])
            return [abs(float(x)) if not self._is_na(x) else x for x in values]
        if name in {"max", "math.max", "min", "math.min"}:
            left, right = self._series(node.args[0]), self._series(node.args[1])
            fn = max if name.endswith("max") else min
            return [
                fn(float(a), float(b)) if not self._is_na(a) and not self._is_na(b) else float("nan")
                for a, b in zip(left, right)
            ]
        if name in {"nz"}:
            values = self._series(node.args[0])
            replacement = self._series(node.args[1]) if len(node.args) > 1 else [0.0] * n
            return [replacement[i] if self._is_na(values[i]) else values[i] for i in range(n)]

        if not name.startswith("ta."):
            raise StrategySpecError(f"unsupported function: {name}")
        fn = name.split(".", 1)[1]
        if fn not in SUPPORTED_TA:
            raise StrategySpecError(f"unsupported ta function: {fn}")

        if fn in {"crossover", "crossunder"}:
            a, b = self._series(node.args[0]), self._series(node.args[1])
            out = [False] * n
            for i in range(1, n):
                if any(self._is_na(x) for x in (a[i], b[i], a[i-1], b[i-1])):
                    continue
                if fn == "crossover":
                    out[i] = a[i] > b[i] and a[i-1] <= b[i-1]
                else:
                    out[i] = a[i] < b[i] and a[i-1] >= b[i-1]
            return out

        if fn == "change":
            a = self._series(node.args[0])
            return [float("nan")] + [
                float(a[i]) - float(a[i-1])
                if not self._is_na(a[i]) and not self._is_na(a[i-1])
                else float("nan")
                for i in range(1, n)
            ]

        if fn == "atr":
            length = self._length(node.args[0])
            tr = [float("nan")] * n
            for i in range(n):
                h, l = self.base["high"][i], self.base["low"][i]
                tr[i] = h - l if i == 0 else max(h - l, abs(h - self.base["close"][i-1]), abs(l - self.base["close"][i-1]))
            return self._rma(tr, length)

        source = self._series(node.args[0])
        length = self._length(node.args[1])
        if fn == "sma":
            out = [float("nan")] * n
            for i in range(length - 1, n):
                window = source[i-length+1:i+1]
                if not any(self._is_na(x) for x in window):
                    out[i] = sum(float(x) for x in window) / length
            return out
        if fn == "ema":
            out = [float("nan")] * n
            alpha = 2.0 / (length + 1.0)
            seed: list[float] = []
            prev = float("nan")
            for i, value in enumerate(source):
                if self._is_na(value):
                    continue
                seed.append(float(value))
                if len(seed) < length:
                    continue
                if self._is_na(prev):
                    prev = sum(seed[-length:]) / length
                else:
                    prev = alpha * float(value) + (1.0 - alpha) * prev
                out[i] = prev
            return out
        if fn in {"highest", "lowest"}:
            out = [float("nan")] * n
            reducer = max if fn == "highest" else min
            for i in range(length - 1, n):
                window = source[i-length+1:i+1]
                clean = [float(x) for x in window if not self._is_na(x)]
                if len(clean) == length:
                    out[i] = reducer(clean)
            return out
        if fn == "rsi":
            changes = [float("nan")] + [
                float(source[i]) - float(source[i-1])
                if not self._is_na(source[i]) and not self._is_na(source[i-1])
                else float("nan")
                for i in range(1, n)
            ]
            gains = [max(0.0, x) if not self._is_na(x) else x for x in changes]
            losses = [max(0.0, -x) if not self._is_na(x) else x for x in changes]
            avg_gain = self._rma(gains, length)
            avg_loss = self._rma(losses, length)
            out = [float("nan")] * n
            for i in range(n):
                if self._is_na(avg_gain[i]) or self._is_na(avg_loss[i]):
                    continue
                if avg_loss[i] == 0:
                    out[i] = 100.0
                else:
                    rs = avg_gain[i] / avg_loss[i]
                    out[i] = 100.0 - 100.0 / (1.0 + rs)
            return out
        raise StrategySpecError(f"unsupported ta function: {fn}")

    @staticmethod
    def _rma(values: list[Any], length: int) -> list[float]:
        out = [float("nan")] * len(values)
        seed: list[float] = []
        prev = float("nan")
        alpha = 1.0 / length
        for i, value in enumerate(values):
            if isinstance(value, float) and math.isnan(value):
                continue
            seed.append(float(value))
            if len(seed) < length:
                continue
            if isinstance(prev, float) and math.isnan(prev):
                prev = sum(seed[-length:]) / length
            else:
                prev = alpha * float(value) + (1.0 - alpha) * prev
            out[i] = prev
        return out


def _metrics(trades: list[dict[str, Any]], equity_curve: list[float], initial: float = 1.0) -> dict[str, Any]:
    returns = [float(x["return"]) for x in trades]
    wins = [x for x in returns if x > 0]
    losses = [x for x in returns if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    peak = initial
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)
    mean = sum(returns) / len(returns) if returns else 0.0
    variance = sum((x - mean) ** 2 for x in returns) / max(1, len(returns) - 1) if len(returns) > 1 else 0.0
    std = math.sqrt(max(0.0, variance))
    return {
        "trade_count": len(trades),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "net_return": (equity_curve[-1] / initial - 1.0) if equity_curve else 0.0,
        "max_drawdown": max_dd,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
        "avg_trade_return": mean,
        "trade_sharpe": (mean / std * math.sqrt(len(returns))) if std > 0 else 0.0,
    }


def run_strategy_spec(
    spec: dict[str, Any],
    bars: list[dict[str, Any]],
    *,
    commission_bps: float = 5.0,
    slippage_bps: float = 2.0,
    active_start: int = 0,
) -> dict[str, Any]:
    if len(bars) < 30:
        raise StrategySpecError("at least 30 bars are required")
    engine = _SeriesEngine(spec, bars)
    long_in = engine.series_for_expr(spec.get("entry_long"))
    short_in = engine.series_for_expr(spec.get("entry_short"))
    long_out = engine.series_for_expr(spec.get("exit_long"))
    short_out = engine.series_for_expr(spec.get("exit_short"))

    realized = 1.0
    equity_curve = [1.0] * len(bars)
    trades: list[dict[str, Any]] = []
    position = 0
    entry_price = 0.0
    entry_index = -1
    entry_equity = 1.0
    cost = commission_bps / 10_000.0
    slip = slippage_bps / 10_000.0

    def exit_position(i: int, raw_price: float) -> None:
        nonlocal realized, position, entry_price, entry_index, entry_equity
        if position == 0:
            return
        fill = raw_price * (1.0 - slip if position > 0 else 1.0 + slip)
        gross = position * (fill / entry_price - 1.0)
        net = gross - cost * 2.0
        realized = entry_equity * (1.0 + net)
        trades.append(
            {
                "side": "long" if position > 0 else "short",
                "entry_index": entry_index,
                "exit_index": i,
                "entry_time": bars[entry_index]["timestamp"],
                "exit_time": bars[i]["timestamp"],
                "entry_price": entry_price,
                "exit_price": fill,
                "return": net,
            }
        )
        position = 0
        entry_price = 0.0
        entry_index = -1
        entry_equity = realized

    def enter_position(i: int, side: int, raw_price: float) -> None:
        nonlocal position, entry_price, entry_index, entry_equity
        position = side
        entry_price = raw_price * (1.0 + slip if side > 0 else 1.0 - slip)
        entry_index = i
        entry_equity = realized

    for i in range(1, len(bars)):
        if i >= max(1, active_start):
            signal_i = i - 1
            desired = 1 if long_in[signal_i] else (-1 if short_in[signal_i] else 0)
            should_exit = (
                (position > 0 and long_out[signal_i])
                or (position < 0 and short_out[signal_i])
            )
            if position != 0 and (should_exit or (desired != 0 and desired != position)):
                exit_position(i, float(bars[i]["open"]))
            if position == 0 and desired != 0:
                enter_position(i, desired, float(bars[i]["open"]))

        close = float(bars[i]["close"])
        if position == 0:
            equity_curve[i] = realized
        else:
            marked = position * (close / entry_price - 1.0) - cost
            equity_curve[i] = entry_equity * (1.0 + marked)

    if position != 0:
        exit_position(len(bars) - 1, float(bars[-1]["close"]))
        equity_curve[-1] = realized

    return {
        "metrics": _metrics(trades, equity_curve),
        "trades": trades,
        "equity_curve": equity_curve,
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "order_model": spec.get("order_model"),
        "sizing_model": spec.get("sizing_model"),
    }


def run_validation(
    spec: dict[str, Any],
    bars: list[dict[str, Any]],
    *,
    folds: int = 5,
    holdout_fraction: float = 0.20,
    commission_bps: float = 5.0,
    slippage_bps: float = 2.0,
) -> dict[str, Any]:
    n = len(bars)
    if n < 120:
        raise StrategySpecError("at least 120 bars are required for walk-forward + holdout")
    holdout_start = max(60, int(n * (1.0 - holdout_fraction)))
    research_end = holdout_start
    fold_size = max(20, research_end // max(1, folds))
    fold_results: list[dict[str, Any]] = []

    for fold in range(folds):
        start = fold * fold_size
        end = research_end if fold == folds - 1 else min(research_end, (fold + 1) * fold_size)
        if end - start < 20:
            continue
        warmup_start = max(0, start - 200)
        subset = bars[warmup_start:end]
        active_start = start - warmup_start
        result = run_strategy_spec(
            spec,
            subset,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            active_start=active_start,
        )
        fold_results.append(
            {
                "fold": fold + 1,
                "start_time": bars[start]["timestamp"],
                "end_time": bars[end - 1]["timestamp"],
                "metrics": result["metrics"],
            }
        )

    holdout = run_strategy_spec(
        spec,
        bars,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        active_start=holdout_start,
    )
    positive_folds = sum(1 for x in fold_results if float(x["metrics"]["net_return"]) > 0)
    traded_folds = sum(1 for x in fold_results if int(x["metrics"]["trade_count"]) > 0)
    wf_pass = bool(
        fold_results
        and traded_folds >= max(2, len(fold_results) // 2)
        and positive_folds >= max(2, math.ceil(len(fold_results) * 0.6))
        and sum(float(x["metrics"]["net_return"]) for x in fold_results) > 0
    )
    hm = holdout["metrics"]
    holdout_pass = bool(
        int(hm["trade_count"]) >= 1
        and float(hm["net_return"]) > 0
        and float(hm["max_drawdown"]) <= 0.30
        and float(hm["profit_factor"]) >= 1.0
    )
    return {
        "walk_forward": {
            "method": "frozen-rule temporal walk-forward; no parameter fitting on future folds",
            "folds": fold_results,
            "positive_folds": positive_folds,
            "traded_folds": traded_folds,
            "passed": wf_pass,
        },
        "holdout": {
            "start_time": bars[holdout_start]["timestamp"],
            "end_time": bars[-1]["timestamp"],
            "fraction": holdout_fraction,
            "metrics": hm,
            "passed": holdout_pass,
        },
        "passed": wf_pass and holdout_pass,
    }
