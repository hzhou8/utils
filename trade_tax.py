#!/usr/bin/python

from datetime import datetime
from datetime import timedelta
import six
import sys
import tempfile
import subprocess
from shutil import copyfile

Trade_Date = 0
Order_Type = 1
Security = 2
Cusip = 3
Description = 4
Quantity = 5
Executed_Price = 6
Commission = 7
Net_Amount = 8

TYPE_BTC = "Buy To Cover"
TYPE_SS = "Sell Short"

STATE_FINDING_MATCH = 1
STATE_FINDING_WASH = 2
STATE_WASH_FOUND = 3
STATE_END = 4


def date_expire_wash(trade_date, prev_date):
    t_date = datetime.strptime(trade_date, '%m/%d/%y')
    p_date = datetime.strptime(prev_date, '%m/%d/%y')
    return (t_date - p_date) > timedelta(30)

def process_trade(data, i, q, dryrun):
    ''' Process a portion of quantity "q" for i-th record.
    :param data:
    :param i:
    :param q:
    :param dryrun:
    :return: the quantity that should be split for processing, or q if no splitting needed.
    '''
    r = data[i]
    assert r['type'] == TYPE_SS
    state = STATE_FINDING_MATCH
    prev_trade = r
    sub = {
        'parent': r,
        'q': q,
        'next': None,
        'prev': None
    }
    prev_sub = sub
    if not dryrun:
        r['remain_q'] -= q
        print "process %s: q = %s, remain_q = %s" % (r['date'], q, r['remain_q'])
        r['sub'].append(sub)

    gain = 0
    for j in range(i + 1, len(data)):
        rj = data[j]
        if rj['remain_q'] == 0:
            continue
        if state == STATE_FINDING_MATCH:
            if rj['type'] == TYPE_SS:
                continue

            if rj['remain_q'] < q:
                return rj['remain_q']

            gain = gain + (prev_sub['parent']['price'] - rj['price'])
            if gain >= 0:
                if not dryrun:
                    print "gain, not wash: %s, %s" % (rj['date'], rj['price'])
                state = STATE_END
            else:
                state = STATE_FINDING_WASH

        elif state == STATE_FINDING_WASH:
            if date_expire_wash(rj['date'], prev_trade['date']):
                if not dryrun:
                    print "not wash: %s, %s" % (prev_trade['date'], q)
                return q

            if rj['type'] == TYPE_BTC:
                continue
            if rj['remain_q'] < q:
                return rj['remain_q']

            if not dryrun:
                print "is wash: %s, %s" % (prev_trade['date'], q)
            state = STATE_FINDING_MATCH

        else:
            raise Exception("Unknown state")

        prev_trade = rj
        sub = {
            'parent': rj,
            'q': q,
            'next': None,
            'prev': prev_sub
        }
        if not dryrun:
            rj['remain_q'] -= q
            prev_sub['next'] = sub
            rj['sub'].append(sub)

        prev_sub = sub
        if state == STATE_END:
            return q

    return q


def find_btc(data, i, q, dryrun):
    ''' Process a portion of quantity "q" for i-th record.
    :param data:
    :param i:
    :param q:
    :param dryrun:
    :return: the quantity that should be split for processing, or q if no splitting needed.
    '''
    r = data[i]
    assert r['type'] == TYPE_SS

    sub = {
        'parent': r,
        'q': q,
        'next': None,
        'prev': None,
        'amount': q * r['price']
    }
    prev_sub = sub
    if not dryrun:
        r['remain_q'] -= q
        if not r['remain_q']:
            sub['amount'] = r['amount'] - (r['quantity'] - q) * r['price']
        #print "process %s: q = %s, remain_q = %s" % (r['date'], q, r['remain_q'])
        r['sub'].append(sub)

    for j in range(i + 1, len(data)):
        rj = data[j]
        if rj['remain_q'] == 0:
            continue

        if rj['type'] == TYPE_SS:
            continue

        if rj['remain_q'] < q:
            return rj['remain_q']

        sub = {
            'parent': rj,
            'q': q,
            'next': None,
            'prev': prev_sub,
            'amount': q * rj['price']
        }
        if not dryrun:
            rj['remain_q'] -= q
            if not rj['remain_q']:
                sub['amount'] = rj['amount'] - (rj['quantity'] - q) * rj['price']
            prev_sub['next'] = sub
            rj['sub'].append(sub)

        return q

    return q


def print_sub(sub, total_gain):
    p = sub['parent']
    prev = sub['prev']
    #amount = sub['q'] * p['price']
    #if p['type'] == TYPE_SS:
    #    commission = sub['q'] * 10 * 0.1 / p['quantity'] * (4.95)
    #    amount -= commission
    #else:
    #    commission = sub['q'] * 10 * 0.1 / p['quantity'] * (4.95)
    #    amount += commission
    #amount = round(amount * 100) / 100
    #print(p['date'], p['type'], "%s/%s" % (sub['q'], p['quantity']), p['price'], amount)
    if p['type'] == TYPE_BTC:
        assert prev
        #prev_commission = sub['q'] * 10 * 0.1 / prev['parent']['quantity'] * (4.95)
        #prev_amount = prev['parent']['price'] * sub['q'] - prev_commission
        #prev_amount = round(prev_amount * 100) / 100

        print("UVXY short %d,%s,%s,%s,%s,,,%s" %
              (sub['q'], prev['parent']['date'], p['date'], sub['amount'],
               sub['prev']['amount'],
               #"yes" if sub['next'] else "No",
               sub['prev']['amount'] - sub['amount']))
        return total_gain + sub['prev']['amount'] - sub['amount']
    return total_gain

def main(argv):
    if len(argv) < 2:
        print "trade_tax.py <trade csv file>"
        exit(0)

    input_file = argv[1]

    data = []
    with file(input_file, 'r') as f:
        for line in f:
            r = line.split(',')

            record = {}
            record['date'] = r[0]
            record['type'] = r[1]
            record['security'] = r[2]
            record['quantity'] = int(r[5])
            record['price'] = float(r[6])
            record['commission'] = r[7]
            record['amount'] = float(r[8])
            if (record['type'] in [TYPE_BTC, TYPE_SS] and
                record['security'] == "UVXY"):
                data.append(record)

    for r in data:
        r['remain_q'] = r['quantity']
        r['sub'] = [] # each sub should have: parent, q, next, prev

    for i in range(len(data)):
        r = data[i]

        if r['type'] == TYPE_BTC and r['remain_q']:
            raise Exception("Type %s shouldn't have remain quantity. Row %s" % (TYPE_BTC, r))

        while (r['remain_q'] > 0):
            ret_q = 0
            sub_q = r['remain_q']
            while ret_q < sub_q:
                sub_q = ret_q if ret_q else r['remain_q']
                ret_q = find_btc(data, i, sub_q, True)
                assert ret_q <= sub_q

            ret_q = find_btc(data, i, sub_q, False)
            assert ret_q == sub_q

    print "Description,Date Acquired,Date sold,Proceeds,Cost basis,Code,Adjustment,Gain or loss"
    count = 0
    btc_count = 0
    total_gain = 0
    for i in range(len(data)):
        r = data[i]
        for sub in r['sub']:
            if not sub['prev']:
                #print "**************"
                total_gain = print_sub(sub, total_gain)
                while sub['next']:
                    sub = sub['next']
                    if (sub['parent']['type'] == TYPE_BTC):
                        btc_count += 1
                    total_gain = print_sub(sub, total_gain)
                count += 1
                #print "===========%s" % count

    #print btc_count
    #print total_gain

    balance = 0
    balance_q = 0
    count = 0
    total_btc = 0
    total_ss = 0
    for r in data:
        amount = r['amount']
        q = r['quantity']
        if r['type'] == TYPE_BTC:
            amount = -amount
            q = -q
            total_btc += amount
        else:
            total_ss += amount

        balance += amount
        balance_q += q
        count += 1


    #print(count, balance, balance_q, total_btc, total_ss)

if __name__ == '__main__':
    main(sys.argv)
