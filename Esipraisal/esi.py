from esipysi import EsiPysi
from urllib.error import HTTPError
import asyncio
import json
import logging

class Esi(object):
    log = logging.getLogger(__name__)

    @classmethod
    def get_client(cls):
        esi_url = "https://esi.evetech.net/_latest/swagger.json?datasource=tranquility"
        ua = "Esipraisal - IGN: Flying Kiwi Sertan"
        return EsiPysi(esi_url, user_agent=ua)
    
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

    def __get_op(self, session, op_name):
        op = None
        try:
            op = session.get_operation(op_name)
        except Exception:
            self.log.exception("Could not get op: {}".format(op_name))
            return
        if op is None:
            self.log.error("Could not get op: {}".format(op_name))
        else:
            return op
    
    async def get_orders_by_region(self, session, region_id, type_id):
        op = self.__get_op(session, "get_markets_region_id_orders")
        params = {"region_id": region_id, "type_id": type_id, "order_type":"all"}
        return await self.__do_request(op, params)

    async def get_market_history_by_region(self, session, region_id, type_id):
        op = self.__get_op(session, "get_markets_region_id_history")
        params = {"region_id": region_id, "type_id": type_id}
        return await self.__do_request(op, params)

    async def get_prices(self, session):
        op = self.__get_op(session, "get_markets_prices")
        return await self.__do_request(op, {})