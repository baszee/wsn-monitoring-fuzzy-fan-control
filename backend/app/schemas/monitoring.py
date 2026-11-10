"""
Skema Pydantic untuk Validasi Request & Response API Monitoring & Kontrol Fan WSN.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class NodeMeasurementResponse(BaseModel):
    """Data pengukuran sensor dan hasil fuzzy terbaru per node."""
    node_id: str
    zone_id: str
    is_active: bool
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    dust_raw_voltage: Optional[float] = None
    pressure_hpa: Optional[float] = None
    rssi: Optional[int] = None
    snr: Optional[float] = None
    dust_index: Optional[float] = None
    condition_score: Optional[float] = None     # s_i
    condition_class: Optional[str] = None       # Baik / Perlu Perhatian / Buruk
    control_level: Optional[float] = None       # u_i
    source_timestamp: Optional[datetime] = None
    status_valid: bool = False
    inputs_complete: bool = False
    is_determining_node: bool = False           # Apakah node ini adalah i* penentu u_zona
    data_age_seconds: Optional[float] = None
    is_fresh: bool = False
    used_for_control: bool = False              # masih di bawah CONTROL_HOLD_SECONDS
    data_status: str = "Tidak ada data"   # Valid | Data lama | Tidak valid | Masukan tidak lengkap | Tidak ada data


class ZoneControlResponse(BaseModel):
    """Keputusan kendali zona dan status perintah fan DC 12V terbaru."""
    zone_id: str
    zone_control_level: Optional[float] = None  # u_zona
    determining_node_id: Optional[str] = None   # i*
    pwm_command_percent: float = 0.0            # Duty cycle PWM (0 - 100%)
    candidate_pwm_percent: Optional[float] = None
    previous_pwm_percent: Optional[float] = None
    auto_pwm_percent: Optional[float] = None
    hysteresis_held: bool = False
    freshness_seconds: int = 30
    control_hold_seconds: int = 600
    determining_data_age_seconds: Optional[float] = None
    using_stale_data: bool = False              # node penentu memakai data lama
    last_evaluated_at: Optional[datetime] = None
    worker_alive: bool = False
    control_status: str                         # Aktif / Mati / Kendali tidak tersedia
    fan_command_status: str                     # Aktif / Mati / Kendali tidak tersedia
    control_mode: str = "auto"                  # auto / manual
    config_version: str
    processing_cycle_id: Optional[str] = None
    created_at: Optional[datetime] = None


class ActiveRuleItem(BaseModel):
    """Rincian aturan fuzzy aktif."""
    id: int
    dust: str
    rh: str
    temp: str
    condition_class: str
    control_level: str
    alpha: float


class FuzzyDetailResponse(BaseModel):
    """Rincian transparansi kalkulasi fuzzy per node (FR-12 & FR-13)."""
    node_id: str
    inputs: Dict[str, Any]
    memberships: Dict[str, Dict[str, float]]
    active_rules: List[ActiveRuleItem]
    outputs: Dict[str, Any]
    curves: Optional[Dict[str, List[float]]] = None


class FuzzySimulateRequest(BaseModel):
    """Request simulasi hipotetis What-If (tanpa efek ke fan)."""
    temperature: float = Field(..., ge=0.0, le=50.0, description="Suhu dalam °C (0 - 50)")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Kelembapan Relatif / RH dalam % (0 - 100)")
    dust_raw: Optional[float] = Field(None, ge=0.0, description="Tegangan sensor debu mentah dalam Volt")
    dust_index: Optional[float] = Field(None, ge=0.0, le=1.0, description="Indeks debu normalisasi (0 - 1)")
    include_curves: bool = Field(False, description="Sertakan kurva semesta output untuk charting")


class FuzzySimulateResponse(BaseModel):
    """Keluaran hasil kalkulasi simulasi What-If."""
    simulated_inputs: Dict[str, Any]
    memberships: Dict[str, Dict[str, float]]
    active_rules: List[ActiveRuleItem]
    outputs: Dict[str, Any]
    curves: Optional[Dict[str, List[float]]] = None
    candidate_pwm_percent: Optional[float] = None   # sebelum histeresis
    config_version: Optional[str] = None
