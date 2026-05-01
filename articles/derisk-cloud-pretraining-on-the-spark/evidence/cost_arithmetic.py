"""Cost arithmetic for derisking a cloud pretrain on the DGX Spark.

Computes the headline tables for the article. Cloud rates are taken from env
vars so the math stays reproducible at any spot-rate envelope:

    H100_HOURLY_USD     # default 2.50  (per-GPU spot, 8×H100 node × $2.50)
    H200_HOURLY_USD     # default 3.50  (per-GPU spot)
    SPARK_KW            # default 0.24  (sustained training draw, kW)
    KWH_USD             # default 0.13  (US 2026 residential avg)
    SPARK_CAPEX_USD     # default 5000
    SPARK_LIFE_YEARS    # default 1.5  (effective amortization horizon)
    ITER_SECONDS        # default 88   (A4 measured wall per iter on Spark)
    CAMPAIGN_ITERS      # default 100
    FINAL_NODE_HOURS    # default 168  (one week of 8×H100 for a 7B Chinchilla)

Run from the article evidence dir:

    python3 cost_arithmetic.py > cost_arithmetic.json

The article quotes rounded-to-the-cent versions of these numbers — re-run
with new rates if cloud spot moves materially and the article copy will need
a refresh.
"""

import json
import os
from dataclasses import dataclass, asdict


def envf(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def envi(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Rates:
    h100_hourly_usd: float
    h200_hourly_usd: float
    spark_kw: float
    kwh_usd: float
    spark_capex_usd: float
    spark_life_years: float
    iter_seconds: int
    campaign_iters: int
    final_node_hours: int

    @property
    def spark_amortized_hourly(self) -> float:
        return self.spark_capex_usd / (self.spark_life_years * 365.25 * 24)

    @property
    def spark_electricity_hourly(self) -> float:
        return self.spark_kw * self.kwh_usd

    @property
    def spark_total_hourly(self) -> float:
        return self.spark_amortized_hourly + self.spark_electricity_hourly

    @property
    def cloud_8xh100_hourly(self) -> float:
        return 8 * self.h100_hourly_usd


def per_iter(hourly: float, iter_seconds: int) -> float:
    return hourly * iter_seconds / 3600.0


def main() -> None:
    rates = Rates(
        h100_hourly_usd=envf("H100_HOURLY_USD", 2.50),
        h200_hourly_usd=envf("H200_HOURLY_USD", 3.50),
        spark_kw=envf("SPARK_KW", 0.24),
        kwh_usd=envf("KWH_USD", 0.13),
        spark_capex_usd=envf("SPARK_CAPEX_USD", 5000.0),
        spark_life_years=envf("SPARK_LIFE_YEARS", 1.5),
        iter_seconds=envi("ITER_SECONDS", 88),
        campaign_iters=envi("CAMPAIGN_ITERS", 100),
        final_node_hours=envi("FINAL_NODE_HOURS", 168),
    )

    spark_iter_electricity = per_iter(rates.spark_electricity_hourly, rates.iter_seconds)
    spark_iter_total = per_iter(rates.spark_total_hourly, rates.iter_seconds)
    h100_iter_single = per_iter(rates.h100_hourly_usd, rates.iter_seconds)
    h100_iter_node = per_iter(rates.cloud_8xh100_hourly, rates.iter_seconds)
    h200_iter = per_iter(rates.h200_hourly_usd, rates.iter_seconds)

    target_scale_iter_node = h100_iter_node * 60.0

    campaign_spark_total = spark_iter_total * rates.campaign_iters
    campaign_spark_electricity = spark_iter_electricity * rates.campaign_iters
    campaign_h100_single = h100_iter_single * rates.campaign_iters
    campaign_h100_node = h100_iter_node * rates.campaign_iters
    campaign_h100_node_target = target_scale_iter_node * rates.campaign_iters

    final_pretrain_node = rates.cloud_8xh100_hourly * rates.final_node_hours

    wrong_pick_rate = 0.50
    expected_loss_blind = wrong_pick_rate * final_pretrain_node
    spark_filter_cost = campaign_spark_total
    expected_savings = expected_loss_blind - spark_filter_cost

    out = {
        "rates": asdict(rates)
        | {
            "spark_amortized_hourly": round(rates.spark_amortized_hourly, 4),
            "spark_electricity_hourly": round(rates.spark_electricity_hourly, 4),
            "spark_total_hourly": round(rates.spark_total_hourly, 4),
            "cloud_8xh100_hourly": round(rates.cloud_8xh100_hourly, 2),
        },
        "per_iter_usd": {
            "spark_electricity_only": round(spark_iter_electricity, 4),
            "spark_total_cost_of_use": round(spark_iter_total, 4),
            "h100_single": round(h100_iter_single, 3),
            "h100_8gpu_node": round(h100_iter_node, 3),
            "h200_single": round(h200_iter, 3),
            "h100_8gpu_node_target_scale_60x": round(target_scale_iter_node, 2),
        },
        "campaign_100_iters_usd": {
            "spark_electricity_only": round(campaign_spark_electricity, 2),
            "spark_total_cost_of_use": round(campaign_spark_total, 2),
            "h100_single_proxy": round(campaign_h100_single, 2),
            "h100_8gpu_node_proxy": round(campaign_h100_node, 2),
            "h100_8gpu_node_target_scale": round(campaign_h100_node_target, 2),
        },
        "final_pretrain_usd": {
            "8xh100_one_week": round(final_pretrain_node, 2),
        },
        "expected_value_argument": {
            "wrong_pick_rate": wrong_pick_rate,
            "expected_loss_from_blind_booking_usd": round(expected_loss_blind, 2),
            "spark_recipe_search_cost_usd": round(spark_filter_cost, 2),
            "expected_savings_per_campaign_usd": round(expected_savings, 2),
            "ratio_savings_to_spark_cost": round(expected_savings / spark_filter_cost, 1)
            if spark_filter_cost > 0
            else None,
        },
        "ratios": {
            "h100_single_vs_spark_electricity": round(
                h100_iter_single / spark_iter_electricity, 1
            ),
            "h100_8gpu_vs_spark_total": round(
                h100_iter_node / spark_iter_total, 1
            ),
            "target_scale_8gpu_vs_spark_total": round(
                target_scale_iter_node / spark_iter_total, 1
            ),
        },
    }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
