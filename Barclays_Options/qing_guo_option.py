import tradersbot as tt
import random
import sys
from scipy.stats import norm
from scipy.optimize import fsolve as solve
import numpy as np
import math

t = tt.TradersBot(host=sys.argv[1], id=sys.argv[2], password=sys.argv[3])

case_length = 450
# Keeps track of prices
SECURITIES = {}
SECURITIES_NEW_PRICE = {}
# Keeps track of the portfolio
PORTFORLIO = {}
# Keep track of the price of the future
Ss = []
# Keep track of the tick
tick = 0
# Keep track of the realized volatility
realized_volatility = []
# Keep track of the orders to be fulfilled
ORDERS = {}
# count = 80



# compute the implied sigma using Black-Scholes
def compute_sigma(t):
	global SECURITIES
	for security in SECURITIES.keys():
		update_sigma(t, security)

# update the sigma
def update_sigma(t, security):
	global SECURITIES
	global NEW_SECURITY_SIGMA
	global case_length
	global Ss
	S = Ss[-1]
	dt = (case_length - t) / case_length / 12
	K = int(security[1:-1])
	C = SECURITIES[security]['price']
	if security[-1:] == "C": # is call option
		SECURITIES[security]['sigma'].append(solve(Black_Scholes_Call(C, S, K, dt), 0.4)[0])
		# print(SECURITIES[security]['sigma'][-1])
	else:
		SECURITIES[security]['sigma'].append(solve(Black_Scholes_Put(C, S, K, dt), 0.4)[0])
		# print(SECURITIES[security]['sigma'][-1])

# return a function of Black-Schole-Call that is dependent on sigma
def Black_Scholes_Call(C, S, K, dt):
	def F(sigma):
		d1 = (np.log(S/K) + (sigma ** 2) * dt/ 2) / (sigma * math.sqrt(dt))
		d2 = d1 - sigma * math.sqrt(dt)
		return norm.cdf(d1) * S - norm.cdf(d2) * K - C
	return F

# return a function of Black-Schole-Put that is dependent on sigma
def Black_Scholes_Put(P, S, K, dt):
	def F(sigma):
		d1 = (np.log(S/K) + (sigma ** 2) * dt/ 2) / (sigma * math.sqrt(dt))
		d2 = d1 - sigma * math.sqrt(dt)
		return norm.cdf(d1) * S - norm.cdf(d2) * K + K - S - P
	return F

# compute the greeks
def compute_greeks(t):
	global SECURITIES
	for security in SECURITIES.keys():
		update_greeks(t, security)

# update the greeks
def update_greeks(t, security):
	global SECURITIES
	global case_length
	global Ss
	S = Ss[-1]
	dt = (case_length - t) / case_length / 12
	sigma = SECURITIES[security]['sigma'][-1]
	K = int(security[1:-1])
	d1 = (np.log(S/K) + (sigma ** 2) * dt/ 2) / (sigma * math.sqrt(dt))
	if security[-1:] == "C": # is call option
		SECURITIES[security]['delta'] = norm.cdf(d1)
	else:
		SECURITIES[security]['delta'] = norm.cdf(d1) - 1
	SECURITIES[security]['gamma'] = norm.pdf(d1) / (S * sigma * math.sqrt(dt))
	SECURITIES[security]['vega'] = S * norm.pdf(d1) * math.sqrt(dt)


####################################### Initialization ###########################################

# Initializes the prices
def ack_register_method(msg, order):
	global SECURITIES
	global PORTFORLIO
	global case_length
	global Ss
	case_length = msg['case_meta']['case_length']
	security_dict = msg['case_meta']['securities']
	PORTFORLIO = {
		'delta' : 0,
		'gamma' : 0,
		'vega' : 0,
	}
	for security in security_dict.keys():
		if not(security_dict[security]['tradeable']): 
			continue
		if security == "TMXFUT":
			Ss = [security_dict[security]['starting_price']]
			continue
		SECURITIES[security] = {
			'price' : security_dict[security]['starting_price'],
			'sigma' : [],
			'delta' : 0,
			'gamma' : 0,
			'vega' : 0,
		}
	compute_sigma(0)
	compute_greeks(0)
	
####################################### market update ###########################################
# Updates latest price
def market_update_method(msg, order):
	global SECURITIES
	global case_length
	global tick
	global Ss
	security = msg['market_state']['ticker']
	new_price = msg['market_state']['last_price']
	tick = msg['elapsed_time']
	if security == "TMXFUT":
		if tick > 2:
			Ss.append(msg['market_state']['last_price'])
	else:
		SECURITIES[security]["price"] = msg['market_state']['last_price']
		update_sigma(tick, security)
		update_greeks(tick, security)


####################################### trader update ###########################################
def compute_rv():
	global Ss
	global case_length
	log_returns = []
	if len(Ss) <= 2:
		return 0
	for i in range(1 , len(Ss)):
		log_returns.append(math.log(Ss[i]) - math.log(Ss[i-1]))
	return np.std(log_returns, ddof = 1) * math.sqrt(case_length * 12)

# Buys or sells in a random quantity every time it gets an update
# You do not need to buy/sell here
def trader_update_method(msg, order):
	global realized_volatility
	global SECURITIES
	global tick
	global ORDERS

	# if tick in ORDERS.keys():
	# 	new_order = ORDERS[tick]
	# 	if new_order[0] == "B":
	# 		order.addBuy(new_order[1], 100)
	# 	else:
	# 		order.addSell(new_order[1], 100)

	# rv = compute_rv()
	# print(rv)
	# if rv == 0:
	# 	return
	# realized_volatility.append(compute_rv())
	# if len(realized_volatility) <= 3 or tick % 2 == 1:
	# 	return

	# if tick >= case_length - 10:
	# 	return

	# diff = realized_volatility[-1] - realized_volatility[-3]
	# max_security = ""
	# max = -1
	# for security in SECURITIES.keys():
	# 	new_val = abs(SECURITIES[security]["sigma"][-3] + diff - SECURITIES[security]["sigma"][-1])
	# 	if new_val > max:
	# 		max = new_val
	# 		max_security = security
	
	# if SECURITIES[max_security]["sigma"][-3] + diff < SECURITIES[max_security]["sigma"][-1]:
	# 	if max_security[-1] == "C":
	# 		order.addSell(max_security, 100)
	# 		ORDERS[tick+10] = ["B", max_security]
	# 	else:
	# 		order.addBuy(max_security, 100)
	# 		ORDERS[tick+10] = ["S", max_security]
	# else:
	# 	if max_security[-1] == "P":
	# 		order.addSell(max_security, 100)
	# 		ORDERS[tick+10] = ["B", max_security]
	# 	else:
	# 		order.addBuy(max_security, 100)
	# 		ORDERS[tick+10] = ["S", max_security]

	# global count
	# vega = 0
	# delta = 0
	# for security in msg["trader_state"]["positions"].keys():
	# 	if msg["trader_state"]["positions"][security] > 0:
	# 		vega += SECURITIES[security]["vega"]
	# 		delta += SECURITIES[security]["delta"]
	# print(msg["trader_state"]["total_fines"] < 0)
	# print(delta * 500)
	# print(vega * 500)
	# print(math.sqrt(-msg["trader_state"]["total_fines"]*1000) + 2000)
	# print(math.sqrt(-msg["trader_state"]["total_fines"]*1000) + 9000)
	# if msg["trader_state"]["total_fines"] == 0:
	# 	order.addBuy("T" + str(count) + "C", 500)
	# 	order.addBuy("T" + str(count) + "P", 500)
	# 	count += 1


###############################################
#### You can add more of these if you want ####
###############################################

t.onAckRegister = ack_register_method
t.onMarketUpdate = market_update_method
t.onTraderUpdate = trader_update_method
#t.onTrade = trade_method
#t.onAckModifyOrders = ack_modify_orders_method
#t.onNews = news_method
t.run()