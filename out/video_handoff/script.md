# Pluma voiceover script

So the obvious question is whether this actually works. We wanted to test it somewhere we could check our answer.

There's a spot in the Great Smoky Mountains called Look Rock, where a camera sits right next to a real air monitor. In November 2016, wildfire smoke moved through that area. We ran our method on seventy-seven daytime photos from that month and compared it to what the monitor recorded.

Our haze measurement matched the instrument on site with a correlation of zero point seven nine. For the PM2.5 number, we calibrated our method on the first half of the month, then tested it on the second half, which it had never seen. On those days the correlation was zero point five one, and we landed in the right air quality category, or the one next to it, ninety percent of the time.

We also want to be honest about what we found. Smoke and summer haze behave differently, so the method needs to be calibrated once for each region and season. It's not something you set once and use forever.

Then we took the same method, with the same calibration, and pointed it at a highway camera here in Arkansas, in the Boston Mountains, where the nearest monitor is forty-six kilometers away. This is the reading it gave us: Good, about three micrograms per cubic meter, somewhere between zero and eighteen. We can't check that number, because there's nothing out there to check it against. And that's really the whole reason we built this.

Where we want to take it next is the highways in the Delta, where the burning happens, so that a school nurse or a clinic could get a heads-up before the smoke arrives.

Dr. Skaug had to go outside and measure the air himself, because nothing else was doing it. The cameras were already there. We just want to put them to use.

This could give many more people access to air quality measurements, and bring air monitoring to many more families.

---

Numbers, all as measured (out/demo/headline.json, site/arkansas/tunnel/series.json):
- 77 = hourly frames that passed the gates and had a site reading (191 fetched, 10:00–16:00, Nov 2016)
- 0.79 = rank correlation, camera vs site extinction (3.912 / visual range)
- 0.51 = rank correlation of PM2.5 on the test half (19–29 Nov, n = 29)
- 90% = within one category on the test half (exact category: 55%)
- Arkansas = ARDOT Tunnel Tower camera, 21 Nov 2026 14:09 CST: 2.9 µg/m³, range 0–18, Good. Single frame, no monitor to check.
