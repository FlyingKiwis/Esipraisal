from esipysi import EsiPysi
from urllib.error import HTTPError
import asyncio
import json
import logging

class Esi():
    log = logging.getLogger(__name__)
    
    def __init__(self, loop=None):
        self.last_error = None
        esi_url = "https://esi.evetech.net/_latest/swagger.json?datasource=tranquility"
        ua = "EsiPyMarket - IGN: Flying Kiwi Sertan"
        if loop is None:
            self.client = EsiPysi(esi_url, user_agent=ua)
        else:
            self.client = EsiPysi(esi_url, loop=loop, user_agent=ua)

    async def __aenter__(self):
        await self.client.start_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.stop_session()

    async def __do_request(self, op, parameters={}, json=True):
        if op is None:
            self.log.error("No operation provided, did the ESI spec change?")
            return None
        try:
            self.log.debug("Executing op \"{}\" - parameters: {}".format(op, parameters))
            result = await op.execute(**parameters)
        except HTTPError as e:
            self.log.error("An error occured with the ESI call \"{}\" - parameters: {} headers: {} status: {} message: {}".format(op, parameters, e.headers, e.code, e.msg))
            self.last_error = e
        except Exception:
            self.log.exception("An exception occured with a ESI call")
            pass
        else:
            self.log.debug("op \"{}\" complete - parameters: {} result: {}".format(op, parameters, result.text))
            if json:
                return result.json()
            return result
        return None

    def __get_op(self, op_name):
        op = None
        try:
            op = self.client.get_operation(op_name)
        except Exception:
            self.log.exception("Could not get op: {}".format(op_name))
            return
        if op is None:
            self.log.error("Could not get op: {}".format(op_name))
        else:
            return op
    
    async def get_orders_by_region(self, region_id, type_id):
        op = self.__get_op("get_markets_region_id_orders")
        params = {"region_id": region_id, "type_id": type_id, "order_type":"all"}
        return await self.__do_request(op, params)

    async def get_market_history_by_region(self, region_id, type_id):
        op = self.__get_op("get_markets_region_id_history")
        params = {"region_id": region_id, "type_id": type_id}
        return await self.__do_request(op, params)

    async def get_prices(self):
        op = self.__get_op("get_markets_prices")
        return await self.__do_request(op, {})