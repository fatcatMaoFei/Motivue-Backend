#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel

from readiness.service import compute_readiness_from_payload
from readiness.cycle_personalization import set_user_cycle_params
from personalization_em_demo import load_personalized_cpt  # global EMISSION_CPT override


app = FastAPI(title="Readiness API", version="1.0")


class ReadinessRequest(BaseModel):
    payload: Dict[str, Any]


class LoadEmissionRequest(BaseModel):
    path: str


class LoadCycleParamsRequest(BaseModel):
    user_id: str
    ov_frac: float
    luteal_off: float
    sig_scale: float


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/readiness")
def readiness(req: ReadinessRequest):
    return compute_readiness_from_payload(req.payload)


@app.post("/personalization/emission/load")
def load_emission(req: LoadEmissionRequest):
    load_personalized_cpt(req.path)
    return {"loaded": req.path}


@app.post("/personalization/cycle/load")
def load_cycle_params(req: LoadCycleParamsRequest):
    set_user_cycle_params(req.user_id, req.ov_frac, req.luteal_off, req.sig_scale)
    return {"user_id": req.user_id, "params": {"ov_frac": req.ov_frac, "luteal_off": req.luteal_off, "sig_scale": req.sig_scale}}

# Run with: uvicorn api.server:app --host 0.0.0.0 --port 8000

