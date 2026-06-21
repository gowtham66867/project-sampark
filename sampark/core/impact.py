from __future__ import annotations


def project_impact(
    outlets: int = 82900,
    monthly_incremental_activations_per_outlet: int = 8,
    annual_value_per_activation_rs: int = 600,
) -> dict[str, int]:
    annual_activations = outlets * monthly_incremental_activations_per_outlet * 12
    annual_value = annual_activations * annual_value_per_activation_rs
    return {
        "outlets": outlets,
        "monthly_incremental_activations_per_outlet": monthly_incremental_activations_per_outlet,
        "annual_incremental_activations": annual_activations,
        "annual_value_rs": annual_value,
        "annual_value_crore_rs": round(annual_value / 10_000_000),
    }

