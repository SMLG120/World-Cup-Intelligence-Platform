"""Aggregate all v1 routers."""
from fastapi import APIRouter

from app.api.v1 import auth, matches, ml, scenarios, simulations, teams, world_cup

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(teams.router)
api_router.include_router(matches.router)
api_router.include_router(simulations.router)
api_router.include_router(scenarios.router)
api_router.include_router(scenarios.admin_router)
api_router.include_router(ml.router)
api_router.include_router(world_cup.router)
