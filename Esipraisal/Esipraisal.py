from .esi import Esi
from .Appraisal import Appraisal
import asyncio
import numpy as np
import itertools
import logging
from datetime import datetime, timedelta, date

logger = logging.getLogger("Esipraisal")

class Esipraisal(object):

    def __init__(self):
        self.__price_table = None
        self.ops = Esi()
        self.client = Esi.get_client()

    async def appraise(self, type_id, region_ids):
        app = Appraisal()
        app.type = type_id
        app.region_list = region_ids

        ccp_val = await self.__value_from_ccp(type_id)

        #Method 1: Orders on market
        order_value = await self.__value_from_orders(type_id, region_ids, ccp_val)

        if order_value is not None:
            app.source = "Market Orders"
            app.value = order_value
            return app

        #Method 2: Historical average
        hist_avg = await self.__value_from_history(type_id, region_ids, ccp_val)
        if hist_avg is not None:
            app.source = "Historical Orders"
            app.value = hist_avg
            return app

        #Method 3:  CCP's value
        if ccp_val is not None:
            app.source = "CCP"
            app.value = ccp_val
            return app

        app.source = "No Valid Source"
        app.value = None
        return app
    
    async def __value_from_orders(self, type_id, region_ids, ccp_value):
        
        async with self.client.session() as esi:
            orders = await self.__fetch_orders(esi, type_id, region_ids)

        price_dicts = self.__to_price_dicts(orders, ccp_value)
        buy_vol = price_dicts.get("buy_volume", 0)
        sell_vol = price_dicts.get("sell_volume", 0)
        min_vol = self.__min_volume(ccp_value)
        logger.debug("Volumes: buy = {} sell = {} min = {}".format(buy_vol, sell_vol, min_vol))
        if buy_vol + sell_vol < min_vol:
            #Exit if volume is too low
            return None

        buy_dict = price_dicts.get("buy")
        sell_dict = price_dicts.get("sell")
        
        volumes = []
        prices = []
        
        for price, volume in buy_dict.items():
            volumes.append(volume)
            prices.append(price)

        for price, volume in sell_dict.items():
            volumes.append(volume)
            prices.append(price)

        if np.sum(volumes) == 0:
            return None

        return np.average(prices, weights=volumes)

    def __min_volume(self, historical_value):
        if historical_value is None:
            return 50

        if historical_value < 1e6:
            return 1000
        if historical_value < 1e9:
            return 100
        return 10

    async def __value_from_history(self, type_id, region_ids, ccp_val):
        async with self.client.session() as esi:
            region_futures = []
            for region in region_ids:
                region_futures.append(self.ops.get_market_history_by_region(esi, region, type_id))

            results = await asyncio.gather(*region_futures)

        prices = []
        volumes = []

        for result in results:
            if result is None:
                continue
            
            if len(result) < 1:
                continue

            valid_count = 0
            indx = len(result) - 1
            while indx > 0 and valid_count < 7:
                data = result[indx]
                logger.debug(data)
                indx -= 1

                price = data.get("average")
                volume = data.get("volume", 0)
                date_str = data.get("date", '1900-01-01')
                data_date = datetime.strptime(date_str, '%Y-%m-%d')

                if data_date + timedelta(days=30) < datetime.utcnow():
                    #Data is too old
                    break

                if self.__is_outlier(price, ccp_val):
                    logger.debug("outlier: price={} ccp_val={}".format(price, ccp_val))
                    continue

                if price is None:
                    continue

                if volume <= 0:
                    continue

                prices.append(price)
                volumes.append(volume)
                valid_count += 1


        if np.sum(volumes) < self.__min_volume(ccp_val):
            logger.debug("Min vol not met: volume={} min vol={}".format(np.sum(volumes), self.__min_volume(ccp_val)))
            return None

        wavg = np.average(prices, weights=volumes)
        return wavg

    async def __value_from_ccp(self, type_id):
        async with self.client.session() as esi:
            self.__price_table = await self.ops.get_prices(esi)
        
        for item_price in self.__price_table:
            if int(item_price.get("type_id")) == int(type_id):
                price = item_price.get("average_price")
                if price is None:
                    price = item_price.get("adjusted_price")
                return price
        
        logger.warning("Could not get price type={}".format(type_id))

    #Fetch orders from region(s) using ESI
    async def __fetch_orders(self, esi, type_id, region_ids):

        region_futures = []
        for region in region_ids:
            region_futures.append(self.ops.get_orders_by_region(esi, region, type_id))

        results = await asyncio.gather(*region_futures)

        combined_results = []

        for result in results:
            if result is None:
                continue
            combined_results = combined_results + result

        return combined_results

    #Get an array of prices for use with statistical analysis
    def __to_price_dicts(self, orders_list, ccp_val):
        n_orders = len(orders_list)
        n = 1
        
        buy_orders = {}
        sell_orders = {}
        buy_volume = 0
        sell_volume = 0


        for order in orders_list:

            buy_order = order.get("is_buy_order")
            price = order.get("price")
            volume = order.get("volume_remain")

            #Outlier filtering
            if self.__is_outlier(price, ccp_val):
                continue

            logger.debug("Processing {} of {} (Volume={})".format(n, n_orders, volume))
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

    def __is_outlier(self, price, average_value):
        if average_value is None:
            return False
        #These should be pretty borad outliers just want to filter out the very low/high
        max_price = average_value * 1.75
        min_price = average_value * 0.25

        if price > max_price:
            logger.debug("Outlier (over): {}".format(price))
            return True
        if price < min_price:
            logger.debug("Outlier (under): {}".format(price))
            return True

        return False



