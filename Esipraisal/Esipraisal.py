from .esi import Esi
from .Appraisal import Appraisal
from .Source import Source
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
        ccp_val = await self.__value_from_ccp(type_id)
        if ccp_val is None:
            estimated_val = None
        else:
            estimated_val = ccp_val.value

        #Method 1: Orders on market
        order_value = await self.__value_from_orders(type_id, region_ids, estimated_val)

        if order_value is not None:
            return order_value

        #Method 2: Historical average
        hist_val = await self.__value_from_history(type_id, region_ids, estimated_val)

        if hist_val is not None:
            return hist_val

        #Method 3:  CCP's value
        if ccp_val is not None:
            ccp_val.region_list = region_ids
            return ccp_val

        app = Appraisal()
        app.source = Source.Invalid
        return app
    
    async def __value_from_orders(self, type_id, region_ids, ccp_value):
        app = Appraisal()
        app.type = type_id
        app.region_list = region_ids
        app.source = Source.MarketOrders

        async with self.client.session() as esi:
            orders = await self.__fetch_orders(esi, type_id, region_ids)

        price_dicts = self.__to_price_dicts(orders, ccp_value)
        buy_vol = price_dicts.get("buy_volume", 0)
        sell_vol = price_dicts.get("sell_volume", 0)
        min_vol = self.__min_volume(ccp_value)
        logger.info("Volumes: buy = {} sell = {} min = {}".format(buy_vol, sell_vol, min_vol))
        if buy_vol + sell_vol < min_vol:
            #Exit if volume is too low
            return None

        buy_dict = price_dicts.get("buy")
        sell_dict = price_dicts.get("sell")
        
        buy_vols = []
        buy_prices = []

        sell_vols = []
        sell_prices = []

        volumes = []
        prices = []
        
        for price, volume in buy_dict.items():
            volumes.append(volume)
            prices.append(price)
            buy_vols.append(volume)
            buy_prices.append(price)

        for price, volume in sell_dict.items():
            volumes.append(volume)
            prices.append(price)
            sell_vols.append(volume)
            sell_prices.append(price)

        vol = np.sum(volumes)
        if vol <= 0:
            return None
        
        buy_vol = np.sum(buy_vols) 
        if buy_vol <= 0:
            return None
        
        sell_vol = np.sum(sell_vols)
        if sell_vol <= 0:
            return None
         
        app.value = np.average(prices, axis=0, weights=volumes)
        app.buy_value = np.average(buy_prices, axis=0, weights=buy_vols)
        app.sell_value = np.average(sell_prices, axis=0, weights=sell_vols)

        app.volume = vol
        app.buy_volume = buy_vol
        app.sell_volume = sell_vol

        return app

    def __min_volume(self, estimated_value):
        if estimated_value is None:
            return 50

        if estimated_value < 1e6:
            return 1000
        if estimated_value < 1e9:
            return 100
        return 10

    async def __value_from_history(self, type_id, region_ids, ccp_val):
        app = Appraisal()
        app.type = type_id
        app.region_list = region_ids
        app.source = Source.HistoricalOrders

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
                logger.info(data)
                indx -= 1

                price = data.get("average")
                volume = data.get("volume", 0)
                date_str = data.get("date", '1900-01-01')
                data_date = datetime.strptime(date_str, '%Y-%m-%d')

                if data_date + timedelta(days=30) < datetime.utcnow():
                    #Data is too old
                    break

                if self.__is_outlier(price, ccp_val):
                    logger.info("outlier: price={} ccp_val={}".format(price, ccp_val))
                    continue

                if price is None:
                    continue

                if volume <= 0:
                    continue

                prices.append(price)
                volumes.append(volume)
                valid_count += 1

        vol = np.sum(volumes)
        if vol < self.__min_volume(ccp_val):
            logger.info("Min vol not met: volume={} min vol={}".format(vol, self.__min_volume(ccp_val)))
            return None

        app.value = np.average(prices, weights=volumes)
        app.volume = vol

        return app

    async def __value_from_ccp(self, type_id):
        app = Appraisal()
        app.type = type_id
        app.source = Source.CCP

        async with self.client.session() as esi:
            self.__price_table = await self.ops.get_prices(esi)
        
        for item_price in self.__price_table:
            if int(item_price.get("type_id")) == int(type_id):
                price = item_price.get("average_price")
                if price is None:
                    price = item_price.get("adjusted_price")
                app.value = price
                return app
        
        logger.warning("Could not get price type={}".format(type_id))
        return None

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



