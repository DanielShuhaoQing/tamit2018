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
	if "elapsed_time" in msg.keys():
		tick = msg['elapsed_time']
	if security == "TMXFUT":
		if tick > 2:
			Ss.append(msg['market_state']['last_price'])
	else:
		SECURITIES[security]["price"] = msg['market_state']['last_price']
		update_sigma(tick, security)
		update_greeks(tick, security)


####################################### trader update ###########################################

def handle_clear(order):
	global ORDERS
	global tick
	if tick in ORDERS.keys():
		new_orders = ORDERS[tick]
		for i in range (0, int(len(new_orders)/3)):
			if new_orders[i*3] == "B":
				order.addBuy(new_orders[i*3+1], new_orders[i*3+2])
			else:
				order.addSell(new_orders[i*3+1], new_orders[i*3+2])

def sticky(option_type, order):
	global ORDERS
	global SECURITIES
	global tick

	ivs = []
	ks = []
	for security in SECURITIES.keys():
		if security[-1] == option_type:
			ivs.append((SECURITIES[security]["sigma"][-3] + SECURITIES[security]["sigma"][-2])/2)
			old_k = int(security[1:-1])
			new_k = old_k / ((Ss[-3] + Ss[-2])/2) * Ss[-1]
			ks.append(new_k)
	poly = np.poly1d(np.polyfit(ks, ivs, 3))
	pos_security = ""
	pos = -1
	neg_security = ""
	neg = -1
	for security in SECURITIES.keys():
		if security[-1] == option_type:
			diff = SECURITIES[security]["sigma"][-1] - poly(int(security[1:-1]))
			new_val = abs(diff)
			if diff < 0:
				if new_val > neg:
					neg = new_val
					neg_security = security
			else:
				if new_val > pos:
					pos = new_val
					pos_security = security
	
	if neg == -1 or pos == -1:
		return
	order.addBuy(neg_security, 100)
	if tick+2 in ORDERS.keys():
		ORDERS[tick+2].extend(["S", neg_security, 100])
	else:
		ORDERS[tick+2]=["S", neg_security, 100]
	order.addSell(pos_security, 100)
	ORDERS[tick+2].extend(["B", pos_security, 100])

	# hedge delta
	delta = 0
	delta -= SECURITIES[neg_security]["delta"]
	delta += SECURITIES[pos_security]["delta"]
	delta = int(delta*100)
	if delta > 0:
		order.addSell("TMXFUT", abs(delta))
		ORDERS[tick+2].extend(["B", "TMXFUT", abs(delta)])
	elif delta < 0:
		order.addBuy("TMXFUT", abs(delta))
		ORDERS[tick+2].extend(["S", "TMXFUT", abs(delta)])

def random_trader(order):
	global ORDERS
	r = random.randint(80,120)
	security = "T" + str(r) + "CP"[random.randint(0,1)]
	order.addSell(security, 100)
	ORDERS[tick+2] = ["B", security, 100]

# Buys or sells in a random quantity every time it gets an update
# You do not need to buy/sell here
def trader_update_method(msg, order):
	global realized_volatility
	global SECURITIES
	global tick
	global ORDERS
	global count
	
	handle_clear(order)

	if tick < 4 or tick % 4 != 0:
		return
	
	sticky("C", order)
	sticky("P", order)

	# random_trader(order)


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