import time
import datetime
import os

os.environ["TZ"] = "UTC"
time.tzset()



utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
cur_year = utc_now.year
day_of_year = utc_now.date().timetuple().tm_yday
cur_year_and_doy=f"{cur_year}-{day_of_year:03}"

print(cur_year_and_doy)


