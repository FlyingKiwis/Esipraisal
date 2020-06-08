# Esipraisal

Esipraisal is a simple tool designed to figure out the value of an item ("type" in the eve DB) based on several sources.


## To Use


[Install with PyPi](https://pypi.org/project/Esipraisal/)


```python
from Esipraisal import Esipraisal
ep = Esipraisal()
await ep.appraise(type_id, region_ids)
```


type_id = The id of the type you want to get the value of

region_ids = a list of region ids in which you want to pull order information from.  Usefull if you say only want mineral prices in Delve.


Returns: Appraisal object


The Appraisal object includes the following info:


* type = the type_id that was appraised
* region_list = the list of region_ids from where the data was pulled
* value = the estimated value of the type
* volume = volume of orders
* buy_value = average value of "buy" orders
* sell_value = average value of "sell" orders
* buy_volume = volume of "buy" orders
* sell_volume = volume of "sell" orders
* source = How the estimate was determined (enum):
    * Market Orders - Most common, from market orders currently active
    * Historical Orders - Past orders which were recently completed, only used if there are not enough market orders for accurate data
    * CCP - CCP's estimate, only used if the above 2 are not valid

Note: volumes listed may be different than those currently listed on market as the volume is after outlier removal has been done
