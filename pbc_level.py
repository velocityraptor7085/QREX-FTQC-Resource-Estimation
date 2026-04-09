from __future__ import annotations

from typing import Any, Dict, Optional
import json

from utils import plot_bar_or_pie, save_json_file, write_csv_file


class PBCResourceEstimator:
    """
    Resource estimator at the PBC (Pauli-Based Computation) level of abstraction.

    Expects an already compiled PBC object (after applying the LitinskiTransformation pass). 
    The estimator tracks counts for PauliEvolutionGate and pauli_product_measurement operations.
    """

    def __init__(self):
        self.last_result: Optional[Dict[str, Any]] = None
        self.last_pbc: Optional[Any] = None

    def estimate_pbc_direct(self, pbc_object: Any) -> Dict[str, Any]:
        """
        Estimates the PBC level resources by counting the number of PauliEvolution 
        and pauli_product_measurement operations.
        """
        
        count_ops_method = getattr(pbc_object, "count_ops", None)
        if count_ops_method is None or not callable(count_ops_method):
            raise TypeError("PBC object must expose a callable count_ops() method.")

        raw_counts = count_ops_method()
        if raw_counts is None:
            raise ValueError("count_ops() returned None; cannot estimate resources.")

        # Count the number of PauliEvolutionGate operations
        pauli_evolution_total = 0
        for op_name, count in dict(raw_counts).items():
            if op_name == "PauliEvolution":
                pauli_evolution_total += int(count)

        # Count the number of product Pauli measurement operations
        pauli_product_measurement_total = 0
        for op_name, count in dict(raw_counts).items():
            if op_name == "pauli_product_measurement":
                pauli_product_measurement_total += int(count)

        # Return a result with high-level PBC circuit information, operation counts and totals
        total_ops = pauli_evolution_total + pauli_product_measurement_total
        result = {
            "pbc": {
                "name": self._safe_name(pbc_object),
                "depth": self._safe_metric(pbc_object, "depth"),
                "width": self._safe_metric(pbc_object, "width"),
                "size": self._safe_metric(pbc_object, "size"),
                "type": type(pbc_object).__name__,
            },
            "operation_counts": {
                "PauliEvolution": int(pauli_evolution_total),
                "pauli_product_measurement": int(pauli_product_measurement_total),
            },
            "totals": {
                "total_ops": int(total_ops),
                "pauli_evolution": int(pauli_evolution_total),
                "pauli_product_measurement": int(pauli_product_measurement_total),
            },
        }

        self.last_result = result
        self.last_pbc = pbc_object
        return result

    def estimate(self, pbc_object: Any) -> Dict[str, Any]:
        # Just to have a consistent API name with estimators at other levels
        return self.estimate_pbc_direct(pbc_object)

    def to_json(self, result: Optional[Dict[str, Any]] = None, indent: int = 2) -> str:
        payload = result if result is not None else self._require_result()
        return json.dumps(payload, indent=indent)

    def save_json(self, output_path: str, result: Optional[Dict[str, Any]] = None, indent: int = 2) -> str:
        payload = result if result is not None else self._require_result()
        return save_json_file(output_path, payload, indent=indent)

    def export_operation_counts_csv(self, output_path: str, result: Optional[Dict[str, Any]] = None) -> str:
        """
        Exports a CSV file with the operations (PauliEvolution and pauli_product_measurement) and their counts.
        """
        payload = result if result is not None else self._require_result()
        rows = [[name, int(count)] for name, count in payload["operation_counts"].items()]
        rows.sort(key=lambda x: (-x[1], x[0]))
        return write_csv_file(output_path, ["operation", "count"], rows)

    def plot_operation_breakdown(
        self,
        result: Optional[Dict[str, Any]] = None,
        chart_type: str = "bar",
        figsize: tuple = (11, 5),
    ):
        """
        Display the PBC operation breakdown as a bar or pie chart.
        Expects the result of `estimate()` or `estimate_pbc_direct()` to be passed in 
        or available from the last estimation.
        """
        payload = result if result is not None else self._require_result()
        counts = dict(payload["operation_counts"])
        if not counts:
            raise ValueError("No operation data available.")

        items = sorted(counts.items(), key=lambda x: x[1], reverse=True) # Sort by descending count
        names, values = zip(*items)

        return plot_bar_or_pie(
            names=names,
            counts=values,
            chart_type=chart_type,
            title="PBC Operation Breakdown",
            xlabel="Operation",
            legend_title="Operation",
            figsize=figsize,
        )

    @staticmethod
    def _safe_name(obj: Any) -> str:
        maybe_name = getattr(obj, "name", None)
        if isinstance(maybe_name, str) and maybe_name.strip():
            return maybe_name
        return "unnamed_pbc_object"

    @staticmethod
    def _safe_metric(obj: Any, method_name: str) -> Optional[int]:
        method = getattr(obj, method_name, None)
        if method is None or not callable(method):
            return None
        try:
            value = method()
            if value is None:
                return None
            return int(value)
        except Exception:
            return None

    def _require_result(self) -> Dict[str, Any]:
        if self.last_result is None:
            raise ValueError("No result available. Run estimate_pbc_direct(...) first.")
        return self.last_result
