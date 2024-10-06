# -*- coding: utf-8 -*-
from userConfig import userconfig, stock_column_tuple, index_column_tuple, db_config
from .object import NumpyFrame, Index#, singleton
from .events import EventBus
from .gate import MySQL_gate
import numpy as np
import pandas as pd
import pickle
import gzip
import joblib
from functools import lru_cache
import datetime
from collections import defaultdict

config = {
    "mod": {
        "stock": {
            "enabled": True,
        },
        "future": {
            "enabled": False,
        }
    }
}

db_start_date="2017-01-01"
db_end_date="2025-01-01"
db_gate = MySQL_gate(
        start_date=db_start_date, 
        end_date=db_end_date, 
        # end_date="2017-02-01", 
        **db_config
    )


def shift_str_date(date_str: str, days_delta: int):
    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    new_date_obj = date_obj + datetime.timedelta(days=days_delta)
    return new_date_obj.strftime("%Y-%m-%d")

# @lru_cache(maxsize=8192)
def transform_key(key):
    if key.endswith('XSHE'):
        return key[:-4] + 'sz'
    elif key.endswith('XSHG'):
        return key[:-4] + 'sh'
    return key

@lru_cache(maxsize=8192)
def trans_name(name):
    if name.lower().endswith('sz'):
        return name[:-2] + 'XSHE'
    elif name.lower().endswith('sh'):
        return name[:-2] + 'XSHG'
    return name


@lru_cache(maxsize=32)
def create_map_dtype(column_tuple):
    column_map = {}
    dtype = []
    for value, item in enumerate(column_tuple):
        column_map[item[0]] = value
        dtype.append((item[0], item[1]))
    return column_map, dtype

class KeyTransDict(dict):
    def __getitem__(self, key):
        key = transform_key(key)
        return super().__getitem__(key)
    
    def __contains__(self, key):
        key = transform_key(key)
        return super().__contains__(key)

import time
def process_stock(stock):
    print(f"{stock} data loading...", end="\r")
    df = db_gate.read_df(stock, db='stock')
    
    if df.empty:
        return
    
    loc_ls = []
    for column in stock_column_tuple:
        loc_ls.append(column[2])
        try:
            # 修改列名
            df.columns.values[column[2]] = column[0]
        except KeyError:
            raise KeyError(f"colume loc {column[2]} not found in {df.columns}")

    df['ts_code'] = df['ts_code'].apply(trans_name)   
    df['date'] = pd.to_datetime(df['date'])

    # 丢弃无关列
    df = df.iloc[:, loc_ls]

    column, dtype = create_map_dtype(stock_column_tuple)
    array = np.array([tuple(row) for row in df.to_records(index=False)], dtype=dtype)

    date_set = set(df['date'])
    all_dates = pd.date_range(start=df['date'].min(), end=df['date'].max())
    start_timestamp = all_dates[0]
    index_array = np.full(len(all_dates), -1, dtype=Index)
    i = 0
        
    for timestamp in all_dates:
        # offset: 第几天, i: 第几个交易日; 
        offset = (timestamp - start_timestamp).days
        assert i <= offset < len(index_array)
        if timestamp in date_set:
            index_array[offset] = Index(None, i, None, timestamp)
            i += 1
        else:
            if i == 0:
                index_array[offset] = Index(None, None, i, timestamp)
            elif i < len(date_set):
                index_array[offset] = Index(i-1, None, i, timestamp)
            else:
                index_array[offset] = Index(i-1, None, None, timestamp)
    # for _ in range(60):
    #     try:
    #         env = Env.get_instance()
    #         break
    #     except:
    #         time.sleep(0.2)
    return stock, NumpyFrame(array, index_array=index_array, start_timestamp=start_timestamp)

def singleton(cls):
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance

@singleton
class Env(object):
    # _env = None

    def __init__(self, config):
        # Env._env = self
        self.config = config
        self.event_bus = EventBus()
        self.usercfg = userconfig
        self.global_vars = None
        self.current_dt = None
        self.trade_dates = None
        self.event_source = None
        self.data = {}#KeyTransDict()
        self.index_data = {}#KeyTransDict()

    # @classmethod
    # def get_instance(cls):
    #     """
    #     返回已经创建的 Environment 对象
    #     """
    #     # if Env._env is None:
    #     #     raise RuntimeError("策略还未初始化")
    #     return Env()

    def set_global_vars(self, global_vars):
        self.global_vars = global_vars

    def set_event_source(self, event_source):
        self.event_source = event_source

    def set_trade_dates(self, trade_dates):
        self.trade_dates = trade_dates

    def load_data(self):
        env = Env()

        # 数据库中的数据时间范围
        db_start_date="2017-01-01"
        db_end_date="2025-01-01"
        db_gate = MySQL_gate(
                start_date=db_start_date, 
                end_date=db_end_date, 
                # end_date="2017-02-01", 
                **db_config
            )

        if_load = env.usercfg['if_load_data']
        if if_load:
            print(datetime.datetime.now())
            # self.data = joblib.load('data.pkl', mmap_mode='r')
            # with gzip.open('data.gz', 'rb') as f:
            #     self.data = pickle.load(f)
            with open('data.pkl', 'rb') as f:
                self.data = pickle.load(f)
            print(datetime.datetime.now())
            # self.index_data = joblib.load('index_data.pkl', mmap_mode='r')
            # with gzip.open('index_data.gz', 'rb') as f:
            #     self.index_data = pickle.load(f)
            with open('index_data.pkl', 'rb') as f:
                self.index_data = pickle.load(f)
            print(datetime.datetime.now())
            # self._dump_data()
            # dt7 = datetime.datetime(2016, 10, 17)
            # dt6 = datetime.datetime(2016, 9, 17)
            # dt2 = datetime.datetime(2020, 9, 17)
            # dt = datetime.datetime(2020, 9, 21)
            # dt3 = datetime.datetime(2020, 9, 18)
            # dt4 = datetime.datetime(2026, 9, 18)
            # dt5 = datetime.datetime(2026, 10, 18)

            # stock = '000001.XSHE'
            # print(self.data[trans_name(stock)][:5, ['open', 'close']])
            # print(self.data[trans_name(stock)][5:, ['open', 'close']])
            # print(self.data[trans_name(stock)][:-5, ['open', 'close']])
            # print(self.data[trans_name(stock)][-5:, ['open', 'close']])
            # print(0)
            # print(self.data[trans_name(stock)][-5:-2, ['open', 'close']])
            # print(self.data[trans_name(stock)][:, ['open', 'close']])
            # print(stock)
            # print(self.data[trans_name(stock)][dt2:dt, ['open', 'close']])
            # print(self.data[trans_name(stock)][dt2:dt3, ['open', 'close']])
            # print(1)
            # print(self.data[trans_name(stock)][dt4:dt5, ['open', 'close']])
            # print(self.data[trans_name(stock)][dt5:dt4, ['open', 'close']])
            # print(2)
            # print(self.data[trans_name(stock)][dt6:dt7, ['open', 'close']])
            # print(self.data[trans_name(stock)][dt7:dt6, ['open', 'close']])
            # print(3)
            # print(self.data[trans_name(stock)][dt7:dt5, ['open', 'close']])
            # print(self.data[trans_name(stock)][dt7:dt3, ['open', 'close']][1])
            # print(4)
            # print(self.data[trans_name(stock)][dt3:dt5, ['open', 'close']][1])

            # pass
            
        else:
            import multiprocessing as mp
            stock_ls = db_gate.get_tables(db='stock').iloc[:, 0]
            with mp.Pool(processes=mp.cpu_count()-1) as pool:
                results = pool.map(process_stock, stock_ls)
            print(len(results))
            for stock, result in results:
                self.data[trans_name(stock)] = result
            # for stock in stock_ls:
            #     print(f"{stock} data loading...", end="\r")
            #     df = db_gate.read_df(stock, db='stock')
                
            #     if df.empty:
            #         continue
            #     loc_ls = []
            #     for column in stock_column_tuple:
            #         loc_ls.append(column[2])
            #         try:
            #             # 修改列名
            #             df.columns.values[column[2]] = column[0]
            #         except KeyError:
            #             raise KeyError(f"colume loc {column[2]} not found in {df.columns}")

            #     df['ts_code'] = df['ts_code'].apply(trans_name)   
            #     df['date'] = pd.to_datetime(df['date'])

            #     # 丢弃无关列
            #     df = df.iloc[:, loc_ls]

            #     column, dtype = create_map_dtype(stock_column_tuple)
            #     array = np.array([tuple(row) for row in df.to_records(index=False)], dtype=dtype)

            #     date_set = set(df['date'])
            #     all_dates = pd.date_range(start=df['date'].min(), end=df['date'].max())
            #     start_timestamp = all_dates[0]
            #     index_array = np.full(len(all_dates), -1, dtype=Index)
            #     i = 0
                    
            #     for timestamp in all_dates:
            #         # offset: 第几天, i: 第几个交易日; 
            #         offset = (timestamp - start_timestamp).days
            #         assert i <= offset < len(index_array)
            #         if timestamp in date_set:
            #             index_array[offset] = Index(None, i, None, timestamp)
            #             i += 1
            #         else:
            #             if i == 0:
            #                 index_array[offset] = Index(None, None, i, timestamp)
            #             elif i < len(date_set):
            #                 index_array[offset] = Index(i-1, None, i, timestamp)
            #             else:
            #                 index_array[offset] = Index(i-1, None, None, timestamp)

            #     self.data[trans_name(stock)] = NumpyFrame(array, index_array=index_array, start_timestamp=start_timestamp)



            index_ls = db_gate.get_tables(db='index').iloc[:, 0]
            for index in index_ls:
                print(f"{index} data loading...", end="\r")
                df = db_gate.read_df(index, db='index')
                if df.empty:
                    continue
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df['date'] = df['trade_date']
                df.set_index('trade_date', inplace=True)
                self.index_data[trans_name(index)] = df

            self._dump_data()
            pass

            

    def _dump_data(self):
        # joblib.dump(self.data, 'data.pkl')
        # joblib.dump(self.index_data, 'index_data.pkl')
        with open('data.pkl', 'wb') as f:
            pickle.dump(self.data, f, protocol=4)
        with open('index_data.pkl', 'wb') as f:
            pickle.dump(self.index_data, f, protocol=4)
        with gzip.open('data.gz', 'wb') as f:
            pickle.dump(self.data, f, protocol=pickle.HIGHEST_PROTOCOL)
        with gzip.open('index_data.gz', 'wb') as f:
            pickle.dump(self.index_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
