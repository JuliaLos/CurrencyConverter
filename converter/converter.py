# Author: Julia Los <los.julia.v@gmail.com>.

"""CurrencyConverter

This module is a currency converter that uses data from the National Bank of the Republic of Belarus
(https://www.nbrb.by).

To convert summa or get rates use the following command:
  converter.py [-h] [--version] [--date DATE] [--rate] [--plot] [summa] currency

Positional arguments:
  summa        the summa to convert (by default, in BYN)
  currency     the alphabetic currency code according to ISO 4217 (use format "FROM-TO" to set target currency
               other than "BYN")

Optional arguments:
  -h, --help   show this help message and exit
  --version    print version info
  --date DATE  the date for rate or the period for plot (in format "YYYY-MM-DD")
  --rate       print the rate on the date
  --plot       make a plot of the rate dynamics for the period

"""

__version__ = '1.0'

import argparse
import functools
import matplotlib.pyplot as plt
import requests
import sys

from datetime import datetime as dt
from requests.exceptions import RequestException


def clear_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        args[0].last_error = None
        return func(*args, **kwargs)
    return wrapper


class CurrencyConverter:
    REQUEST_CURRENCIES = 'https://www.nbrb.by/api/exrates/currencies'
    REQUEST_RATES = 'https://www.nbrb.by/api/exrates/rates'
    REQUEST_DYNAMICS = 'https://www.nbrb.by/api/exrates/rates/dynamics'

    def __init__(self):
        self.last_error = None

    @staticmethod
    def _make_request(request, params=None):
        """Make request and return response."""
        response, error = {}, None
        try:
            r = requests.get(request, params=params, timeout=(2, 5))
            r.raise_for_status()
            response = r.json()
        except RequestException as e:
            error = e
        finally:
            return response, error

    @clear_error
    def make_plot(self, val, start_date, end_date):
        """ This function makes a plot of the rate dynamics over the period.
            It receives:
               val - the currency code
               start_date - the beginning of period in format 'YYYY-MM-DD'
               end_date - the end of period in format 'YYYY-MM-DD'
        """
        if val.upper() == 'BYN':
            return

        beg_period = dt.strptime(start_date, '%Y-%m-%d')
        end_period = dt.strptime(end_date, '%Y-%m-%d')

        response, error = self._make_request(self.REQUEST_CURRENCIES)
        if error:
            self.last_error = str(error)
            return

        vals = [{'Cur_ID': res.get('Cur_ID'),
                 'Cur_DateStart': dt.strptime(res.get('Cur_DateStart'), '%Y-%m-%dT%H:%M:%S'),
                 'Cur_DateEnd': dt.strptime(res.get('Cur_DateEnd'), '%Y-%m-%dT%H:%M:%S')}
                for res in response if res.get('Cur_Abbreviation', '') == val.upper()]
        filter_period = (lambda x: x['Cur_DateStart'] <= beg_period <= x['Cur_DateEnd'] or
                         x['Cur_DateStart'] <= end_period <= x['Cur_DateEnd'])
        vals = list(filter(filter_period, vals))

        if len(vals) == 0:
            self.last_error = f'Currency "{val.upper()}" not found'
            return

        rates = {}
        for item in vals:
            val_code = item.get('Cur_ID')
            params = {'startdate': max([beg_period, item.get('Cur_DateStart')]).strftime('%Y-%m-%d'),
                      'enddate': min([end_period, item.get('Cur_DateEnd')]).strftime('%Y-%m-%d')}
            response, error = self._make_request(f'{self.REQUEST_DYNAMICS}/{val_code}', params)
            if error:
                self.last_error = str(error)
                return
            rates.update({dt.strptime(rate.get('Date'), '%Y-%m-%dT%H:%M:%S'): rate.get('Cur_OfficialRate')
                          for rate in response})

        plt.style.use('seaborn')
        fig, ax = plt.subplots()
        ax.set_title('The rate dynamics')
        ax.set_ylabel('Rates (BYN)')
        ax.plot(rates.keys(), rates.values(), '-o', label=val.upper())
        fig.autofmt_xdate()
        ax.autoscale()
        ax.legend()
        plt.show()

    @clear_error
    def get_rate(self, val, date=None):
        """ This function finds rate of currency in BYN.
            It receives:
               val - the currency code
               date - the date in format 'YYYY-MM-DD'
            It returns a tuple with currency scale and rate.
        """
        if val.upper() == 'BYN':
            return 1.0, 1.0

        params = {'parammode': 2}
        if date:
            params['ondate'] = date
        response, error = self._make_request(f'{self.REQUEST_RATES}/{val.upper()}', params)
        if error:
            self.last_error = str(error)
            return 1.0, 0.0
        return response.get('Cur_Scale', 1.0), response.get('Cur_OfficialRate', 0.0)

    @clear_error
    def convert(self, summa, from_val, to_val="BYN", date=None):
        """ This function converts summa from one currency to other currency.
            It receives:
                summa - the summa to convert
                from_val - the source currency code
                to_val - the target currency code
                date - the date in format 'YYYY-MM-DD'
            It returns a summa in the target currency.
        """
        if from_val.upper() == to_val.upper():
            return summa

        summa_in_byn = summa
        if from_val.upper() != "BYN":
            rate = self.get_rate(from_val, date)
            if self.last_error:
                return 0.0
            summa_in_byn = summa / rate[0] * rate[1]

        rate = self.get_rate(to_val, date)
        if self.last_error:
            return 0.0
        return summa_in_byn / rate[1] * rate[0]


def _get_args(argv):
    """Parsing command-line arguments."""
    parser = argparse.ArgumentParser(prog='converter.py', description='Python command-line currency converter')
    parser.add_argument('--version', action='version', version='"Version {version}"'.format(version=__version__),
                        help='print version info')
    parser.add_argument('summa', type=float, nargs='?', default=1.0,
                        help='the summa to convert')
    parser.add_argument('currency', type=str,
                        help=('the alphabetic currency code according to ISO 4217 '
                              '(use format "FROM-TO" to set target currency other than "BYN")'))
    parser.add_argument('--date', nargs=2 if '--plot' in argv[1:] else None, required=('--plot' in argv[1:]),
                        help='the date for rate or the period for plot (in format "YYYY-MM-DD")')
    parser.add_argument('--rate', action='store_true', default=False,
                        help='print the rate on the date')
    parser.add_argument('--plot', action='store_true', default=False,
                        help='make a plot of the rate dynamics for the period')
    return parser.parse_args(argv[1:])


def main():
    args = _get_args(sys.argv)
    c = CurrencyConverter()
    if args.plot:
        c.make_plot(args.currency, args.date[0], args.date[1])
        if c.last_error:
            print(c.last_error)
    else:
        if args.rate:
            rate = c.get_rate(args.currency, args.date)
            if c.last_error:
                print(c.last_error)
            else:
                print(f'{rate[0]} {args.currency.upper()}: {rate[1]} BYN')
        else:
            vals = args.currency.split('-')
            from_val = vals[0] if len(vals) > 1 else args.currency
            to_val = vals[1] if len(vals) > 1 else 'BYN'
            summa = c.convert(args.summa, from_val, to_val, args.date)
            if c.last_error:
                print(c.last_error)
            else:
                print(f'{args.summa} {from_val.upper()} = {summa:.4f} {to_val.upper()}')


if __name__ == "__main__":
    main()
