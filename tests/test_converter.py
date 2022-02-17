import argparse
import pytest
import requests
import requests_mock

from contextlib import nullcontext
from converter.converter import CurrencyConverter, get_args
from datetime import datetime
from io import StringIO
from unittest import mock

TEST_DATA_RATE_1 = {'Cur_Scale': 1.0,
                    'Cur_OfficialRate': 2.0,
                    }
TEST_DATA_RATE_2 = {'Cur_Scale': 10.0,
                    'Cur_OfficialRate': 2.0,
                    }
TEST_DATA_VAL_1 = [{'Cur_ID': 159,
                    'Cur_Scale': 1.0,
                    'Cur_Abbreviation': 'USD',
                    'Cur_DateStart': '2020-01-01T00:00:00',
                    'Cur_DateEnd': '2050-01-01T00:00:00',
                    }]
TEST_DATA_VAL_2 = [{'Cur_ID': 159,
                    'Cur_Scale': 10.0,
                    'Cur_Abbreviation': 'USD',
                    'Cur_DateStart': '2020-01-01T00:00:00',
                    'Cur_DateEnd': '2050-01-01T00:00:00',
                    }]
TEST_DATA_DYN_1 = [{'Date': '2022-02-14T00:00:00',
                    'Cur_OfficialRate': 2.0,
                    }]
TEST_DATA_DYN_2 = [{'Date': '2022-02-01T00:00:00',
                    'Cur_OfficialRate': 2.0,
                    },
                   {'Date': '2022-02-14T00:00:00',
                    'Cur_OfficialRate': 2.5,
                    }]


@pytest.mark.parametrize(
    "command,expected",
    [
        (['converter.py', '100', 'usd'],
         {'summa': 100.0, 'currency': 'usd', 'date': None, 'rate': False, 'plot': False}),
        (['converter.py', '100', 'usd-eur', '--date', '2022-02-14'],
         {'summa': 100.0, 'currency': 'usd-eur', 'date': '2022-02-14', 'rate': False, 'plot': False}),
        (['converter.py', 'usd', '--rate'],
         {'summa': 1.0, 'currency': 'usd', 'date': None, 'rate': True, 'plot': False}),
        (['converter.py', '100', 'usd', '--rate', '--date', '2022-02-14'],
         {'summa': 100.0, 'currency': 'usd', 'date': '2022-02-14', 'rate': True, 'plot': False}),
        (['converter.py', 'usd', '--plot', '--date', '2022-02-01', '2022-02-14'],
         {'summa': 1.0, 'currency': 'usd', 'date': ['2022-02-01', '2022-02-14'], 'rate': False, 'plot': True}),
    ],
)
def test_get_args_correct(command, expected):
    assert get_args(command) == argparse.Namespace(**expected)


@pytest.mark.parametrize(
    "command,exception,expected",
    [
        (['converter.py', '100', 'usd'], nullcontext(), [""]),
        (['converter.py', '100', 'usd', '--date', '2022-02-01', '2022-02-14'], pytest.raises(SystemExit),
         ["error: unrecognized arguments: 2022-02-14"]),
        (['converter.py', 'usd', 'eur', '--rate'], pytest.raises(SystemExit),
         ["error: argument summa: invalid float value: 'usd'"]),
        (['converter.py', '--rate', '--date', '2022-02-14'], pytest.raises(SystemExit),
         ["error: the following arguments are required: currency"]),
        (['converter.py', 'usd', '--plot', '--date', '2022-02-01'], pytest.raises(SystemExit),
         ["error: argument --date: expected 2 arguments"]),
    ],
)
def test_get_args_incorrect(command, exception, expected):
    with mock.patch('sys.stderr', new_callable=StringIO) as mock_stderr:
        with exception:
            get_args(command)
            assert expected[0] in mock_stderr.getvalue()


@pytest.mark.parametrize(
    "params,exception",
    [
        ({'exc': requests.exceptions.ConnectionError}, [requests.exceptions.ConnectionError]),
        ({'exc': requests.exceptions.URLRequired}, [requests.exceptions.URLRequired]),
        ({'exc': requests.exceptions.Timeout}, [requests.exceptions.Timeout]),
        ({'status_code': 404}, [requests.exceptions.HTTPError]),
        ({'text': 'json'}, [requests.exceptions.JSONDecodeError]),
    ],
)
def test_make_request(params, exception):
    with requests_mock.Mocker() as m:
        m.get(f'{CurrencyConverter.REQUEST_RATES}/USD?parammode=2', **params)
        try:
            assert CurrencyConverter().convert(100, 'usd') == 0.0
        except exception[0]:
            assert False, f'function _make_request() raised an exception: {exception[0]}'


@pytest.mark.parametrize(
    "args,params,expected",
    [
        (['usd'], TEST_DATA_RATE_1, (1.0, 2.0)),
        (['usd', '2022-02-14'], TEST_DATA_RATE_2, (10.0, 2.0)),
        ([100.0, 200.0], TEST_DATA_RATE_1, (1.0, 0.0)),
        (['100', 'date'], TEST_DATA_RATE_2, (1.0, 0.0)),
        ([None, None], TEST_DATA_RATE_1, (1.0, 0.0)),
        ([100, 'usd'], {}, (1.0, 0.0)),
    ],
)
def test_get_rate(args, params, expected):
    with requests_mock.Mocker() as m:
        m.get(f'{CurrencyConverter.REQUEST_RATES}/USD?parammode=2', json=params)
        try:
            assert CurrencyConverter().get_rate(*args) == expected
        except Exception as e:
            assert False, f'function get_rate() raised an exception: {e}'


@pytest.mark.parametrize(
    "args,params,expected",
    [
        ([100, 'usd'], TEST_DATA_RATE_1, [200.0]),
        ([100.0, 'usd', 'byn', '2022-02-14'], TEST_DATA_RATE_2, [20.0]),
        ([100.0, 'byn', 'usd', '2022-02-14'], TEST_DATA_RATE_1, [50.0]),
        (['100', 'usd', 'byn', '2022-02-14'], TEST_DATA_RATE_2, [0.0]),
        ([100, 200, 300, 400], TEST_DATA_RATE_1, [0.0]),
        ([100, '200', 'date'], TEST_DATA_RATE_2, [0.0]),
        ([None, None, None], TEST_DATA_RATE_1, [0.0]),
        ([100, 'byn', 'usd'], {}, [0.0]),
        ([100, 'usd'], {}, [0.0]),
    ],
)
def test_convert(args, params, expected):
    with requests_mock.Mocker() as m:
        m.get(f'{CurrencyConverter.REQUEST_RATES}/USD?parammode=2', json=params)
        try:
            assert CurrencyConverter().convert(*args) == expected[0]
        except Exception as e:
            assert False, f'function convert() raised an exception: {e}'


@pytest.mark.parametrize(
    "args,params1,params2,expected",
    [
        (['usd', '2022-02-01', '2022-02-14'], TEST_DATA_VAL_1, TEST_DATA_DYN_1,
         (1.0,
          {datetime(2022, 2, 14, 0, 0): 2.0})
         ),
        (['usd', '2022-02-14', '2022-02-01'], TEST_DATA_VAL_2, TEST_DATA_DYN_2,
         (10.0,
          {datetime(2022, 2, 1, 0, 0): 2.0,
           datetime(2022, 2, 14, 0, 0): 2.5})
         ),
        (['usd', '2020-02-01', '2022-02-01'], TEST_DATA_VAL_1, TEST_DATA_DYN_1, (1.0, {})),
        (['100', '2022-02-01', '2022-02-14'], TEST_DATA_VAL_2, TEST_DATA_DYN_2, (1.0, {})),
        ([100, 200, 300], TEST_DATA_VAL_1, TEST_DATA_DYN_1, (1.0, {})),
        (['usd', 'date', 'date'], TEST_DATA_VAL_2, TEST_DATA_DYN_2, (1.0, {})),
        ([None, None, None], TEST_DATA_VAL_1, TEST_DATA_DYN_1, (1.0, {})),
        (['usd', '2022-02-01', '2022-02-14'], [], TEST_DATA_DYN_2, (1.0, {})),
        (['usd', '2022-02-01', '2022-02-14'], TEST_DATA_VAL_1, [], (1.0, {})),
    ],
)
def test_get_rate_dynamics(args, params1, params2, expected):
    with requests_mock.Mocker() as m:
        m.get(CurrencyConverter.REQUEST_CURRENCIES, json=params1)
        m.get(f'{CurrencyConverter.REQUEST_DYNAMICS}/159', json=params2)
        try:
            assert CurrencyConverter().get_rate_dynamics(*args) == expected
        except Exception as e:
            assert False, f'function get_rate_dynamics() raised an exception: {e}'
