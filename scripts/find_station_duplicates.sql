select * from stations where "StationCode" in (select "StationCode" from 
(select distinct "StationCode", count("StationCode") as sumstn
 	from stations group by "StationCode") as query1
where sumstn > 1) order by "StationCode"
