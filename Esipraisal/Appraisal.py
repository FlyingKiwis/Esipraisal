

class Appraisal(object):

    def __init__(self):
        self.type = None
        self.value = None
        self.source = None
        self.region_list = None

    def __str__(self):
        return "Value: {}, Source: {} type={} regions={}".format(self.value, self.source, self.type, self.region_list)