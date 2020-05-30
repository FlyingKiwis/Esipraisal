from esi import Esi
from Appraisal import Appraisal
import asyncio
import numpy as np
import itertools


class Esipraisal(object):

    def __init__(self):
        self.__price_table = None


    async def appraise(self, type_id, region_ids):
        app = Appraisal()
        app.type = type_id
        app.region_list = region_ids

        #Method 1: Orders on market
        hist_avg = await self.__value_from_history(type_id, region_ids)
        if hist_avg is None:
            order_value = None
        else:
            order_value = await self.__value_from_orders(type_id, region_ids, hist_avg)

        if order_value is not None:
            app.source = "Market Orders"
            app.value = order_value
            return app

        #Method 2: Historical average
        if hist_avg is not None:
            app.source = "Historical Orders"
            app.value = hist_avg
            return app

        #Method 3:  CCP's value
        ccp_val = await self.__value_from_ccp(type_id)

        if ccp_val is not None:
            app.source = "CCP"
            app.value = ccp_val
            return app

        app.source = "No Valid Source"
        app.value = None
        return app
    
    async def __value_from_orders(self, type_id, region_ids, historical_value):
        
        async with Esi() as esi:
            orders = await self.__fetch_orders(esi, type_id, region_ids)

        price_dicts = self.__to_price_dicts(orders, historical_value)
        buy_vol = price_dicts.get("buy_volume", 0)
        sell_vol = price_dicts.get("sell_volume", 0)
        min_vol = self.__min_volume(historical_value)
        print("buy = {} sell = {} min = {}".format(buy_vol, sell_vol, min_vol))
        if buy_vol + sell_vol < min_vol:
            #Exit if volume is too low
            return None

        sorted_orders = self.__sort_trim_orders(price_dicts)
        buy_dict = sorted_orders.get("buy")
        sell_dict = sorted_orders.get("sell")
        
        volumes = []
        prices = []
        
        for price, volume in buy_dict.items():
            volumes.append(volume)
            prices.append(price)

        for price, volume in sell_dict.items():
            volumes.append(volume)
            prices.append(price)

        return np.average(prices, weights=volumes)

    def __min_volume(self, historical_value):
        if historical_value < 1e3:
            return 1e5
        if historical_value < 1e6:
            return 1e4
        if historical_value < 1e8:
            return 1000
        if historical_value < 1e9:
            return 100
        return 10

    async def __value_from_history(self, type_id, region_ids):
        async with Esi() as esi:
            region_futures = []
            for region in region_ids:
                region_futures.append(esi.get_market_history_by_region(region, type_id))

            results = await asyncio.gather(*region_futures)

        prices = []
        volumes = []

        for result in results:
            if result is None:
                continue
            
            if len(result) < 1:
                continue

            last = result[-1]
            price = last.get("average")
            volume = last.get("volume", 0)

            if price is None:
                continue

            if volume <= 0:
                continue

            prices.append(price)
            volumes.append(volume)

        if len(prices) < 1:
            return None

        wavg = np.average(prices, weights=volumes)
        return wavg

    async def __value_from_ccp(self, type_id):
        if self.__price_table is None:
            async with Esi() as esi:
                self.__price_table = esi.get_prices()
        
        for item_price in self.__price_table:
            if item_price.get("type_id") == type_id:
                return item_price.get("average_price")
        

    #Fetch orders from region(s) using ESI
    async def __fetch_orders(self, esi, type_id, region_ids):

        region_futures = []
        for region in region_ids:
            region_futures.append(esi.get_orders_by_region(region, type_id))

        results = await asyncio.gather(*region_futures)

        combined_results = []

        for result in results:
            if result is None:
                continue
            combined_results = combined_results + result

        return combined_results

    #Get an array of prices for use with statistical analysis
    def __to_price_dicts(self, orders_list, recent_average=-1):
        n_orders = len(orders_list)
        n = 1
        
        buy_orders = {}
        sell_orders = {}
        buy_volume = 0
        sell_volume = 0
        filter_outliers = recent_average > 0
        #These should be pretty borad outliers just want to filter out the very low/high
        max_price = recent_average * 1.5
        min_price = recent_average * 0.5


        for order in orders_list:

            buy_order = order.get("is_buy_order")
            price = order.get("price")
            volume = order.get("volume_remain")

            #Outlier filtering
            if filter_outliers:
                if price > max_price:
                    continue
                if price < min_price:
                    continue

            print("Processing {} of {} (Volume={})".format(n, n_orders, volume))
            n += 1

            if buy_order:
                buy_volume += volume
                if price in buy_orders:
                    buy_orders[price] = buy_orders[price] + volume
                else:
                    buy_orders[price] = volume
            else:
                sell_volume += volume
                if price in sell_orders:
                    sell_orders[price] = sell_orders[price] + volume
                else:
                    sell_orders[price] = volume
        
        return {"buy":buy_orders, "buy_volume": buy_volume, "sell":sell_orders, "sell_volume": sell_volume}

    def __sort_trim_orders(self, price_dicts):
        buy_dict = price_dicts.get("buy")
        buy_volume = price_dicts.get("buy_volume")
        buy_trim_volume = min(max(100, round(buy_volume*0.05)), buy_volume)
        sorted_buy = dict(sorted(buy_dict.items(), reverse=True))

        current_vol = 0
        indx = 0
        trimmed_buy = dict()
        while current_vol < buy_trim_volume and indx < len(sorted_buy):
            vol = list(sorted_buy.values())[indx]
            if vol + current_vol > buy_trim_volume:
                vol = buy_trim_volume - current_vol
            trimmed_buy[list(sorted_buy.keys())[indx]] = vol
            current_vol += vol
            indx += 1

        sell_dict = price_dicts.get("sell")
        sell_volume = price_dicts.get("sell_volume")
        sell_trim_volume = min(max(100, round(sell_volume*0.05)), sell_volume)
        sorted_sell = dict(sorted(sell_dict.items()))

        current_vol = 0
        indx = 0
        trimmed_sell = dict()
        while current_vol < sell_trim_volume and indx < len(sorted_sell):
            vol = list(sorted_sell.values())[indx]
            if vol + current_vol > buy_trim_volume:
                vol = buy_trim_volume - current_vol
            trimmed_sell[list(sorted_sell.keys())[indx]] = vol
            current_vol += vol
            indx += 1

        return {"buy":trimmed_buy, "sell":trimmed_sell}

