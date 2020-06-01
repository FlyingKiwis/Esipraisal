import asyncio
from Esipraisal.Esipraisal import Esipraisal

ep = Esipraisal()
region_ids=[10000002, 10000043, 10000032, 10000016, 10000042, 10000030, 10000064, 10000033, 10000068, 10000020]
app = asyncio.run(ep.appraise(20454, region_ids))
#Plex

print(app)