from tradersbot import *
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import sys

t = TradersBot(host=sys.argv[1], id=sys.argv[2], password=sys.argv[3])
# Initialize variables: positions, expectations, future customer orders, etc
position_limit = 5000
case_length = 450

SECURITIES = {
    'TRDRS.LIT': 0,
    'TRDRS.DARK': 0
}
SOURCES = {}
DARKORDER = {
    'isBuy': False,
    'size': 0,
    'source': ''
}
tick = -20
p2tick = -20
p2 = -1
clearOutTick = -20

# Used for debug
def print_msg(msg):
    print("=================\n", msg, "\n================\n")

# Used to determine the point of time that we clear out the position
def p2p4Calculation():
    global SOURCES
    global DARKORDER
    global clearOutTick
    global p2tick
    clearAtP2 = SOURCES[DARKORDER['source']] > 0
    clearOutTick = p2tick + 1 if clearAtP2 else p2tick + 4

def register(msg, TradersOrder):
    global SECURITIES
    global SOURCES
    global tick
    security_dict = msg['case_meta']['securities']
    for security in security_dict.keys():
        SECURITIES[security] = security_dict[security]['starting_price']
    source_dict = msg['case_meta']['news_sources']
    for source in source_dict.keys():
        SOURCES[source] = 0
    tick = msg['elapsed_time']
    

def update_market(msg, TradersOrder):
    global SECURITIES
    global tick
    tick = msg['elapsed_time']
    SECURITIES[msg['market_state']['ticker']] = msg['market_state']['last_price']


def update_trader(msg, TradersOrder):
    global tick
    global p2tick
    global SECURITIES
    global DARKORDER
    global case_length
    global position_limit
    global SOURCES
    global p2
    global clearOutTick
    lit_position = msg['trader_state']['positions']['TRDRS.LIT']
    dark_position = msg['trader_state']['positions']['TRDRS.DARK']
    all_position = lit_position + dark_position
    all_position_abs = abs(all_position)
    # handle buy dark
    if tick == p2tick - 1:
        if DARKORDER['isBuy']:
            target_min = SECURITIES['TRDRS.LIT']
            TradersOrder.addSell('TRDRS.DARK', position_limit, target_min + 10)
            #TODO
        else:
            target_min = SECURITIES['TRDRS.LIT']
            TradersOrder.addBuy('TRDRS.DARK', position_limit, target_min - 10)

    # cancel unfulfilled dark orders
    if tick == p2tick + 1 and msg['trader_state']['open_orders'] != {}:
        for order in msg['trader_state']['open_orders'].keys():
            TradersOrder.addCancel('TRDRS.DARK', order)

    # Buy(sell) to maximize(minimize) position
    if tick < p2tick and tick <= case_length - 15:
        if all_position_abs < position_limit:
            for i in range(0, int((position_limit - all_position_abs) / 1000)):
                if DARKORDER['isBuy']:
                    TradersOrder.addBuy('TRDRS.LIT', 1000)
                else:
                    TradersOrder.addSell('TRDRS.LIT', 1000)
            if DARKORDER['isBuy'] and (position_limit - all_position_abs) % 1000 > 0:
                TradersOrder.addBuy('TRDRS.LIT', (position_limit - all_position_abs) % 1000)
            else:
                TradersOrder.addSell('TRDRS.LIT', (position_limit - all_position_abs) % 1000)

    if tick == p2tick + 1:
        p2 = SECURITIES['TRDRS.LIT'] if DARKORDER['isBuy'] else  -SECURITIES['TRDRS.LIT']
    if tick == p2tick + 4:
        p4 = SECURITIES['TRDRS.LIT'] if DARKORDER['isBuy'] else  -SECURITIES['TRDRS.LIT']
        print("\ncurrent tick is ", tick, "\n")
        print_msg(clearOutTick)
        print_msg(SOURCES)
        print_msg(p2)
        print_msg(p4)
        SOURCES[DARKORDER['source']] += (1 if p2 > p4 else -1)
    
    # need to clear out the position
    if tick >= clearOutTick or tick > case_length - 15: # TODO
        if all_position > 0:
            for i in range(0, int(all_position_abs / 1000)):
                TradersOrder.addSell('TRDRS.LIT', 1000)
            if all_position_abs % 1000 > 0:
                TradersOrder.addSell('TRDRS.LIT', all_position_abs % 1000)
        else:
            for i in range(0, int(all_position_abs / 1000)):
                TradersOrder.addBuy('TRDRS.LIT', 1000)
            if all_position_abs % 1000 > 0:
                TradersOrder.addBuy('TRDRS.LIT', all_position_abs % 1000)

def update_trade(msg, TradersOrder):
    # Update trade information
    pass

def update_order(msg, TradersOrder):
    # Update order information
    pass

def update_news(msg, TradersOrder):
    global DARKORDER
    global p2tick
    global tick
    global case_length
    global position_limit
    DARKORDER['isBuy'] = 'buy' in msg['news']['headline']
    DARKORDER['size'] = int(msg['news']['body'])
    DARKORDER['source'] = msg['news']['source']
    tick = msg['news']['time']
    p2tick = tick + 8

    p2p4Calculation()

    if tick > case_length - 15:
        return  # TODO

    for i in range(0, int(position_limit / 1000)):
        if DARKORDER['isBuy']:
            TradersOrder.addBuy('TRDRS.LIT', 1000)
        else:
            TradersOrder.addSell('TRDRS.LIT', 1000)

t.onAckRegister = register
t.onMarketUpdate = update_market
t.onTraderUpdate = update_trader
# t.onTrade = update_trade
# t.onAckModifyOrders = update_order
t.onNews = update_news

t.run()

## Haven't make use of p1, haven't make history update of choosing p2 and p4, haven't make use of source.