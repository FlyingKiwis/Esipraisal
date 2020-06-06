import asyncio
import logging
from Esipraisal.Esipraisal import Esipraisal

ep_log = logging.getLogger("Esipraisal")
ep_log.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
ep_log.addHandler(ch)


ep = Esipraisal()
region_ids=[10000002, 10000043, 10000032, 10000016, 10000042, 10000030, 10000064, 10000033, 10000068, 10000020, 10000040, 10000013, 10000039, 10000058]
app = asyncio.run(ep.appraise(29988, region_ids))

print(app)