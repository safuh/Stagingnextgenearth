"""Climate data provider adapters."""

from stagingnextgenearth.providers.chirps import CHIRPSProvider
from stagingnextgenearth.providers.copernicus import CopernicusERA5Provider
from stagingnextgenearth.providers.nasa_power import NASAPowerProvider

__all__ = ["CHIRPSProvider", "CopernicusERA5Provider", "NASAPowerProvider"]
