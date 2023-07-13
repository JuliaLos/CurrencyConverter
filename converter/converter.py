# Author: Julia Los <los.julia.v@gmail.com>.

"""CurrencyConverter

This module is a currency converter that uses data from the National Bank of the Republic of Belarus
(https://www.nbrb.by).

It can be used as Command line tool. In this case, to convert summa or get rates use the following command:
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
  --plot       make a plot of the rate dynamics for the period (no more than 365 days)

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
    REQUEST_CURRENCIES = 'https://api.nbrb.by/exrates/currencies'
    REQUEST_RATES = 'https://api.nbrb.by/exrates/rates'
    REQUEST_DYNAMICS = 'https://api.nbrb.by/exrates/rates/dynamics'

    DATE_LONG = '%Y-%m-%dT%H:%M:%S'
    DATE_SHORT = '%Y-%m-%d'

    def __init__(self):
        self.last_error = None

    @staticmethod
    def _check_val_code(val):
        """Check the currency code is correct."""
        if isinstance(val, str):
            return (len(val) == 3) and val.isalpha()
        return False

    @staticmethod
    def _date_to_str(date, to_format):
        """Convert date to string."""
        date_string = None
        try:
            date_string = date.strftime(to_format)
        except (TypeError, ValueError):
            pass
        return date_string

    @staticmethod
    def _date_from_str(date_string, from_format):
        """Convert string to date."""
        date = None
        try:
            date = dt.strptime(date_string, from_format)
        except (TypeError, ValueError):
            pass
        return date

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
    def get_rate_dynamics(self, val, start_date, end_date):
        """ This function finds rate of currency in BYN for the period.
            It receives:
               val - the currency code
               start_date - the beginning of period in format 'YYYY-MM-DD'
               end_date - the end of period in format 'YYYY-MM-DD'
            It returns a tuple with currency scale and dictionary with rates for the period.
        """
        if not self._check_val_code(val):
            self.last_error = f'The currency code "{val}" is incorrect'
            return 1.0, {}

        if val.upper() == 'BYN':
            self.last_error = ''
            return 1.0, {}

        beg_period = self._date_from_str(start_date, self.DATE_SHORT)
        end_period = self._date_from_str(end_date, self.DATE_SHORT)

        if not beg_period:
            self.last_error = f'The date "{start_date}" is incorrect'
            return 1.0, {}

        if not end_period:
            self.last_error = f'The date "{end_date}" is incorrect'
            return 1.0, {}

        if beg_period > end_period:
            beg_period, end_period = end_period, beg_period

        if (end_period - beg_period).days > 365:
            self.last_error = f'The period from {beg_period:%Y-%m-%d} to {end_period:%Y-%m-%d}" is more than 365 days'
            return 1.0, {}

        response, error = self._make_request(self.REQUEST_CURRENCIES)
        if error:
            self.last_error = str(error)
            return 1.0, {}

        vals = [{'Cur_ID': res.get('Cur_ID'),
                 'Cur_Scale': res.get('Cur_Scale', 1.0),
                 'Cur_DateStart': self._date_from_str(res.get('Cur_DateStart'), self.DATE_LONG),
                 'Cur_DateEnd': self._date_from_str(res.get('Cur_DateEnd'), self.DATE_LONG)}
                for res in response if res.get('Cur_Abbreviation', '') == val.upper()]
        filter_period = (lambda x: (x['Cur_DateStart'] and x['Cur_DateEnd'] and
                                    (x['Cur_DateStart'] <= beg_period <= x['Cur_DateEnd'] or
                                     x['Cur_DateStart'] <= end_period <= x['Cur_DateEnd'])))
        vals = list(filter(filter_period, vals))

        if len(vals) == 0:
            self.last_error = f'The currency "{val.upper()}" not found'
            return 1.0, {}

        rates = {}
        scale = sorted(vals, key=lambda x: (x['Cur_DateStart'], x['Cur_DateEnd']))[-1]['Cur_Scale']

        for v in vals:
            val_code = v.get('Cur_ID')
            params = {'startdate': self._date_to_str(max([beg_period, v.get('Cur_DateStart')]), self.DATE_SHORT),
                      'enddate': self._date_to_str(min([end_period, v.get('Cur_DateEnd')]), self.DATE_SHORT)}
            response, error = self._make_request(f'{self.REQUEST_DYNAMICS}/{val_code}', params)
            if error:
                self.last_error = str(error)
                return {}
            rates.update({self._date_from_str(rate.get('Date'), self.DATE_LONG): (rate.get('Cur_OfficialRate') *
                                                                                  scale / v.get('Cur_Scale'))
                          for rate in response})

        if len(rates) == 0:
            self.last_error = f'The rates for currency "{val.upper()}" not found'
            return 1.0, {}

        return scale, rates

    @clear_error
    def make_plot(self, val, start_date, end_date):
        """ This function makes a plot of the rate dynamics for the period.
            It receives:
               val - the currency code
               start_date - the beginning of period in format 'YYYY-MM-DD'
               end_date - the end of period in format 'YYYY-MM-DD'
        """
        scale, rates = self.get_rate_dynamics(val, start_date, end_date)
        if len(rates) == 0:
            return

        plt.style.use('seaborn')
        fig, ax = plt.subplots()
        fig.canvas.manager.set_window_title('The rate dynamics')
        ax.set_title(f'The rates of {scale:.0f} {val.upper()} in BYN')
        ax.plot(rates.keys(), rates.values(), '-o', label=f'{scale:.0f} {val.upper()}')
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
        if not self._check_val_code(val):
            self.last_error = f'The currency code "{val}" is incorrect'
            return 1.0, 0.0

        if val.upper() == 'BYN':
            return 1.0, 1.0

        params = {'parammode': 2}
        if date:
            if not self._date_from_str(date, self.DATE_SHORT):
                self.last_error = f'The date "{date}" is incorrect'
                return 1.0, 0.0
            params['ondate'] = date

        response, error = self._make_request(f'{self.REQUEST_RATES}/{val.upper()}', params)
        if error:
            self.last_error = str(error)
            return 1.0, 0.0

        if len(response) == 0:
            self.last_error = f'The rate for currency "{val.upper()}" not found'
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
        if not isinstance(summa, (int, float)):
            self.last_error = f'The summa "{summa}" is incorrect'
            return 0.0

        if not self._check_val_code(from_val):
            self.last_error = f'The currency code "{from_val}" is incorrect'
            return 0.0

        if not self._check_val_code(to_val):
            self.last_error = f'The currency code "{to_val}" is incorrect'
            return 0.0

        if from_val.upper() == to_val.upper():
            return summa

        summa_in_byn = summa
        if from_val.upper() != 'BYN':
            rate = self.get_rate(from_val, date)
            if self.last_error:
                return 0.0
            summa_in_byn = summa / rate[0] * rate[1] if rate[0] != 0 else 0.0

        rate = self.get_rate(to_val, date)
        if self.last_error:
            return 0.0
        return summa_in_byn / rate[1] * rate[0] if rate[1] != 0 else 0.0


def get_args(argv):
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
    args = get_args(sys.argv)
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
