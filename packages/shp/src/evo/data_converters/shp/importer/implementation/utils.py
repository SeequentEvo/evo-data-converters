#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from datetime import date, datetime, timedelta

_EPOCH = datetime(1970, 1, 1)


def datetime_to_evo_timestamp(dt: datetime) -> int | None:
    if dt is None:
        return None

    try:
        ts = dt.timestamp() * 1_000_000
    except OSError:
        # Occurs if the date is 1970/1/1 or earlier.
        td = dt - _EPOCH
        ts = td / timedelta(microseconds=1)
    return int(ts)


def date_to_evo_timestamp(d: date) -> int | None:
    if d is None:
        return None

    return datetime_to_evo_timestamp(datetime(d.year, d.month, d.day))
