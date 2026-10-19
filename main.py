"""Wing lift demo backend.

Uses thin-airfoil theory (Cl = 2*pi*sin(alpha)) below stall,
a simple post-stall decay above it, and a lifting-line induced-drag model.
"""

import math
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

RHO = 1.225          # air density, kg/m^3 (sea level)
STALL_DEG = 15.0     # stall angle of attack
CL_MAX = 2 * math.pi * math.sin(math.radians(STALL_DEG))
OSWALD = 0.85        # span efficiency
CD0 = 0.008          # parasitic drag coefficient

app = FastAPI(title="Wing Lift Demo")
TEMPLATES = Path(__file__).parent / "templates"


def cl_of(alpha_deg: float) -> float:
    """Lift coefficient with a simple stall model."""
    sign = 1.0 if alpha_deg >= 0 else -1.0
    a = abs(alpha_deg)
    if a <= STALL_DEG:
        return sign * 2.0 * math.pi * math.sin(math.radians(a))
    # post-stall: linear decay toward ~25% of CLmax at 60 deg
    frac = max(0.0, 1.0 - (a - STALL_DEG) / 45.0)
    return sign * CL_MAX * (0.25 + 0.75 * frac)


def cd_of(alpha_deg: float, cl: float, aspect_ratio: float) -> float:
    """Drag: parasitic + induced + separation drag after stall."""
    cd = CD0 + cl * cl / (math.pi * OSWALD * max(aspect_ratio, 1e-6))
    a = abs(alpha_deg)
    if a > STALL_DEG:
        cd += 1.1 * math.sin(math.radians(a - STALL_DEG))
    return cd


@app.get("/", response_class=HTMLResponse)
def index():
    return (TEMPLATES / "index.html").read_text(encoding="utf-8")


@app.get("/api/lift")
def lift(
    alpha: float = Query(6.0, ge=-10, le=45, description="Angle of attack [deg]"),
    v: float = Query(60.0, gt=0.5, le=300, description="Airspeed [m/s]"),
    chord: float = Query(1.2, gt=0.05, le=20, description="Chord length [m]"),
    span: float = Query(6.0, gt=0.05, le=40, description="Span [m]"),
):
    ar = span / chord
    cl = cl_of(alpha)
    cd = cd_of(alpha, cl, ar)
    q = 0.5 * RHO * v * v                 # dynamic pressure
    s = chord * span                       # wing area
    lift_n = q * s * cl
    drag_n = q * s * cd
    gamma = cl * v * chord                 # circulation [m^2/s]
    downwash_rad = cl / (math.pi * ar)     # induced downwash angle
    return {
        "alpha_deg": alpha,
        "cl": round(cl, 4),
        "cd": round(cd, 4),
        "lift_n": round(lift_n, 1),
        "drag_n": round(drag_n, 1),
        "ld": round(lift_n / drag_n, 2) if drag_n else None,
        "gamma": round(gamma, 2),
        "downwash_deg": round(math.degrees(downwash_rad), 2),
        "q_pa": round(q, 1),
        "stalled": abs(alpha) > STALL_DEG,
        "cl_max": round(CL_MAX, 3),
        "stall_deg": STALL_DEG,
    }


@app.get("/api/cl-curve")
def cl_curve(step: float = Query(0.5, gt=0.05)):
    """Full Cl-vs-alpha curve (including stall) for the chart."""
    out = []
    a = -6.0
    while a <= 40.0 + 1e-9:
        out.append({"alpha": round(a, 2), "cl": round(cl_of(a), 4)})
        a += step
    return {"points": out, "stall_deg": STALL_DEG, "cl_max": CL_MAX}