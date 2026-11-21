"""Look Rock (GRSM) regions for 1000x750 archive frames (2016 framing).

Distances are from the NPS landmark chart (old nature.nps.gov "Landmarks" tab),
converted from miles. Box positions were placed by mapping the chart onto the
2016 frame (same ~43 deg field of view; frame = 1.82 * chart + (45, 12) px)
and checked against computed elevation angles of each summit.
Boxes sample each landmark's face just below its skyline.
"""
MILE = 1609.344

# name: (distance_miles, (x0, x1, y0, y1))
LANDMARKS = {
    "Happy Valley Ridge": (1, (450, 620, 500, 530)),
    "Beard Cane Mtn":     (5, (650, 720, 440, 460)),
    "Cades Cove":         (8, (790, 860, 425, 435)),
    "Rich Mtn":           (10, (450, 540, 380, 395)),
    "Thunderhead Mtn":    (15, (830, 960, 352, 368)),
    "Cove Mountain":      (19, (70, 150, 395, 410)),
    "Clingmans Dome":     (26, (630, 700, 366, 376)),
    "Mt LeConte":         (29, (335, 375, 375, 388)),
    "Mt Guyot":           (40, (235, 285, 386, 393)),
}

# Sky just above the skyline, left/centre where ridges are lowest.
SKY = (50, 600, 322, 342)

# Foreground canopy next to the tower (~50 m). Haze barely affects it, so its
# change between frames measures the lighting/exposure change (gain).
FOREGROUND = (40, 420, 640, 740)
