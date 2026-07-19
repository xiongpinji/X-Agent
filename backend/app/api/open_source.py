from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.open_source_api import OpenSourceCandidateRecord, OpenSourceDiscoveryReport, open_source_discovery_store
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
