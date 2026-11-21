"""NPS AirWebCams archive (Look Rock = location 'grsm').

Search returns per-frame metadata including the site's hourly sensor values.
Units, from NPS's 2016 Look Rock webcam JSON: PM2.5 in ug/m3, visual range in km
(the archive's VisualRange cannot be miles: max 243 would imply < Rayleigh extinction).
Images are fetched one at a time by the caller (fetch_frame), never in bulk loops.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

SEARCH = "https://www.nps.gov/airwebcams/api/Search/Execute"
HIRES = "https://www.nps.gov/airwebcams/GetAsset/{}/proxy/hires"


def search_day(date_mdy: str, location: str = "grsm") -> dict:
    body = {
        "Operand": {"LeftOperand": {"MatchType": "Exact", "Term": "LocationCode", "Attribute": location},
                    "RightOperand": {"CompareType": "=", "Term": "ImageCreateDate", "Attribute": date_mdy},
                    "Operator": "AND"},
        "ActionFilter": "Search", "StatusFilter": "Active",
        "SortTerms": [{"Term": "CreateDate", "Ascending": True}], "PageSize": 300,
        "ResultTerms": ["ImageCreateDate", "CustomTextFields", "CustomNumberFields", "AdditionalMetadata"],
        "CurrentPage": 1,
    }
    req = urllib.request.Request(SEARCH, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "pluma-research"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def records(result: dict) -> list[dict]:
    out = []
    for r in result.get("Results", []):
        a = r["Asset"]
        v = {x["Name"]: x["Value"] for x in a["CustomNumberFields"]}
        v["time"] = a["LocalTimeString"]
        v["asset"] = a["AssetID"]
        out.append(v)
    return out


def fetch_frame(asset_id: str, dest: Path) -> int:
    req = urllib.request.Request(HIRES.format(asset_id), headers={"User-Agent": "pluma-research"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    dest.write_bytes(data)
    return len(data)


if __name__ == "__main__":
    import sys
    date, out = sys.argv[1], Path(sys.argv[2])
    res = search_day(date)
    out.write_text(json.dumps(res))
    recs = records(res)
    noon = [x for x in recs if " 12:00 PM" in x["time"] or " 1:00 PM" in x["time"]]
    print(date, len(recs), "frames;", [(x["time"].split(" ")[1] + x["time"].split(" ")[2], x.get("ParticulateMatter"),
                                       x.get("VisualRange"), x.get("RelativeHumidity")) for x in noon])
