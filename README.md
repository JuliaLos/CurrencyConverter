# CurrencyConverter

This module is a currency converter that uses data from the National Bank of the Republic of Belarus (https://www.nbrb.by).

## Command line tool

To convert summa or get rate use the following command:

    converter.py [-h] [--version] [--date DATE] [--rate] [--plot] [summa] currency

_Positional arguments:_

    summa        the summa to convert
    currency     the alphabetic currency code according to ISO 4217 (use format "FROM-TO" to set target currency other than "BYN")

_Optional arguments:_

    -h, --help   show this help message and exit
    --version    print version info
    --date DATE  the date for rate or the period for plot (in format "YYYY-MM-DD")
    --rate       print the rate on the date
    --plot       make a plot of the rate dynamics for the period

## Python API

At first, create the currency converter object:

    >>> from converter import CurrencyConverter
    >>> c = CurrencyConverter()

To convert from EUR to USD on 14 February 2022 use:

    >>> c.convert(100, 'EUR', 'USD', '2022-02-14')
    113.7411

To get the rate of RUB in BYN on 01 February 2022 use:

    # function return tulpe (<scale>, <rate>)
    >>> c.get_rate('RUB', '2022-02-01')
    (100.0, 3.3551) 

To make a plot of the rate dynamics for the period from 01 February 2022 to 14 February 2022 use:

    # function open window with the plot of the rate dynamics
    >>> c.make_plot('USD', '2022-02-01', '2022-02-14')