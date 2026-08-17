"""Minimal stand-in for the Prosperity ``datamodel`` module.

The real file is distributed with the competition. This shim exists so the
reference strategies in ``strategies/`` can be imported and replayed offline
without it. It implements only what those strategies touch.
"""
from __future__ import annotations

from dataclasses import dataclass, field

Symbol = str
Product = str
UserId = str


@dataclass
class Order:
    symbol: Symbol
    price: int
    quantity: int  # positive = buy, negative = sell


@dataclass
class OrderDepth:
    buy_orders: dict[int, int] = field(default_factory=dict)   # price -> +qty
    sell_orders: dict[int, int] = field(default_factory=dict)  # price -> -qty


@dataclass
class Trade:
    symbol: Symbol
    price: int
    quantity: int
    buyer: UserId | None = None
    seller: UserId | None = None
    timestamp: int = 0


@dataclass
class TradingState:
    timestamp: int = 0
    traderData: str = ""
    listings: dict = field(default_factory=dict)
    order_depths: dict[Symbol, OrderDepth] = field(default_factory=dict)
    own_trades: dict[Symbol, list[Trade]] = field(default_factory=dict)
    market_trades: dict[Symbol, list[Trade]] = field(default_factory=dict)
    position: dict[Product, int] = field(default_factory=dict)
    observations: object = None
