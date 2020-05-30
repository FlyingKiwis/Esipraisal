# Esipraisal

Esipraisal is a simple tool designed to figure out the value of an item ("type" in the eve DB) based on several sources.


## To Use


[Install with PyPi](https://pypi.org/project/Esipraisal/)


```python
import Esipraisal
Esipraisal.appraise(type_id, region_ids)
```


type_id = The id of the type you want to get the value of
region_ids = a list of region ids in which you want to pull order information from.  Usefull if you say only want mineral prices in Delve.


Returns: Appraisal object


The Appraisal object includes the following info:


* type = the type_id that was appraised
* region_list = the list of region_ids from where the data was pulled
* value = the estimated value of the type
* source = How the estimate was determined:
    * Market Orders - Most common, from market orders currently active
    * Historical Orders - Past orders which were recently completed, only used if there are not enough market orders for accurate data
    * CCP - CCP's estimate, only used if the above 2 are not valid
