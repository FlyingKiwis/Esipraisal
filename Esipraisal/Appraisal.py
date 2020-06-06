

class Appraisal(object):

    def __init__(self):
        self.type = None
        self.source = None
        self.region_list = None

        self.value = None
        self.volume = None

        self.buy_value = None
        self.buy_volume = None

        self.sell_value = None
        self.sell_volume = None

    def __str__(self):
        return "Value={} Volume={} Source: {} type={} regions={}\nBuy: price={} volume={}\nSell: price={} volume={}".format(self.value, self.volume, self.source, self.type, self.region_list, self.buy_value, self.buy_volume, self.sell_value, self.sell_volume)