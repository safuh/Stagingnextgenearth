# Copernicus ERA5 climate ingestion

The platform includes an optional Copernicus Climate Data Store (CDS) adapter
for hourly ERA5 single-level reanalysis. It complements (rather than replaces)
NASA POWER daily point observations and CHIRPS v3 daily precipitation rasters.

## Enablement

Install the optional provider libraries into the application environment:

```bash
uv pip install "cdsapi>=0.7.7" "xarray>=2024.1.0" "netCDF4>=1.6"
```

These packages are intentionally not part of the default locked runtime; deployments
that do not enable ERA5 do not need them.

Create a CDS account, accept the ERA5 dataset terms in the CDS web interface,
and configure the official CDS API client credentials using the instructions
at <https://cds.climate.copernicus.eu/en/how-to-api>. Keep the token in the
runtime secret store or the operator's private CDS API configuration; never
commit it to the repository or expose it to the browser.

The adapter uses dataset `reanalysis-era5-single-levels`, NetCDF output, and
the official `cdsapi` client. Retrieval is blocking upstream work and is
executed off the asyncio event loop. The request window is capped (seven days
by default), and area extraction is capped (2,500 grid cells by default).
Increase these limits only after capacity, storage and CDS usage have been
reviewed.

## Supported defaults

| CDS variable | Platform variable |
|---|---|
| `2m_temperature` | `air_temperature_2m` |
| `total_precipitation` | `precipitation` |

ERA5 is hourly and grid-based. A point request selects the nearest grid cell
inside a small request envelope; an area request returns grid-cell
measurements. The source units are preserved unchanged. In particular,
ERA5 total precipitation is not silently converted from metres to millimetres.

## Scientific and operational safeguards

- Dataset terms must be accepted by the CDS account before retrieval.
- Every output records dataset, source variable, citation, licence and temporal
  resolution in measurement metadata.
- Provider ingestion remains separate from platform quality review. Imported
  values must enter the existing pending-review workflow.
- ERA5 is a reanalysis product, not a direct station observation. Do not merge
  it with station observations without retaining source, resolution, units and
  quality status.
- CDS jobs may queue or fail. Operators should schedule ingestion with bounded
  windows, retry at the orchestration layer, and retain the returned request
  provenance.
- The current adapter supports ERA5 single-level variables only. It does not
  provide CMIP6 projections, ensemble uncertainty, bias correction or
  downscaling.

Official references:
- <https://cds.climate.copernicus.eu/en/how-to-api>
- <https://cds.climate.copernicus.eu/api/retrieve/v1/docs>
- <https://doi.org/10.24381/cds.adbb2d47>
