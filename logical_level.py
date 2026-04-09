from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, Optional
import json

from qiskit import transpile
from qiskit.circuit import QuantumCircuit
from qiskit.quantum_info import get_clifford_gate_names

from utils import plot_bar_or_pie, save_json_file, write_csv_file


class LogicalResourceEstimator:
    """
    Logical level resource estimation, which analyzes a quantum circuit by
    transpiling it to a basis of logically implementable Clifford + T gates,
    which can be specified by the user. 

    For example, the demo uses a basis of `get_clifford_gate_names() + ["t", "tdg"]`
    and `get_clifford_gate_names() + ["rz", "t", "tdg"]` as a suitable basis as these
    are common logical implementable gate sets for fault-tolerant schemes. This is
    described in more detail in the "A Game of Surface Codes" paper by Litinski (https://arxiv.org/abs/1808.02892). 

    Classification is operation-name based from circuit.count_ops():
        - clifford: in get_clifford_gate_names()
        - non_unitary: in DEFAULT_NON_UNITARY_OPERATIONS
        - non_clifford: everything else
    """

    DEFAULT_NON_UNITARY_OPERATIONS = {"measure", "reset", "barrier", "delay", "snapshot"}

    def __init__(
        self,
        clifford_gates: Optional[Iterable[str]] = None,
        non_unitary_gates: Optional[Iterable[str]] = None,
    ):
        self.clifford_gates = set(clifford_gates or get_clifford_gate_names())
        self.non_unitary_gates = set(non_unitary_gates or self.DEFAULT_NON_UNITARY_OPERATIONS)
        self.last_result: Optional[Dict[str, Any]] = None
        self.last_circuit: Optional[QuantumCircuit] = None

    def estimate_circuit(
        self,
        circuit: QuantumCircuit,
        transpile_first: bool = False,
        transpile_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Transpile the circuit to the appropriate basis (if not already done)
        analyzed = transpile(circuit, **(transpile_kwargs or {})) if transpile_first else circuit
        op_counts = Counter(dict(analyzed.count_ops()))

        categorized = {
            "clifford": Counter(),
            "non_clifford": Counter(),
            "non_unitary": Counter(),
        }

        # Count the number of clifford vs non-clifford vs non-unitary gates
        for gate_name, count in op_counts.items():
            if gate_name in self.non_unitary_gates:
                categorized["non_unitary"][gate_name] += count
            elif gate_name in self.clifford_gates:
                categorized["clifford"][gate_name] += count
            else:
                categorized["non_clifford"][gate_name] += count

        # Compute totals for each class
        clifford_total = sum(categorized["clifford"].values())
        non_clifford_total = sum(categorized["non_clifford"].values())
        non_unitary_total = sum(categorized["non_unitary"].values())

        # Return a result dictionary with high-level circuit information, logical gate counts by class, totals, and a raw count of all gates
        result = {
            "circuit": {
                "name": analyzed.name or "unnamed_circuit",
                "num_qubits": analyzed.num_qubits,
                "num_clbits": analyzed.num_clbits,
                "depth": analyzed.depth(),
                "width": analyzed.width(),
                "size": analyzed.size(),
            },
            "gate_counts": {
                "clifford": dict(categorized["clifford"]),
                "non_clifford": dict(categorized["non_clifford"]),
                "non_unitary": dict(categorized["non_unitary"]),
            },
            "totals": {
                "total_ops": int(sum(op_counts.values())),
                "clifford": int(clifford_total),
                "non_clifford": int(non_clifford_total),
                "non_unitary": int(non_unitary_total),
                "unitary": int(clifford_total + non_clifford_total),
                "t": int(categorized["non_clifford"].get("t", 0)),
                "tdg": int(categorized["non_clifford"].get("tdg", 0)),
                "t_like": int(categorized["non_clifford"].get("t", 0) + categorized["non_clifford"].get("tdg", 0)),
            },
            "raw_count_ops": dict(op_counts),
        }

        self.last_result = result
        self.last_circuit = analyzed
        return result

    def estimate(
        self,
        circuit: QuantumCircuit,
        transpile_first: bool = False,
        transpile_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Just to have a more consistent API name with other levels
        return self.estimate_circuit(circuit, transpile_first=transpile_first, transpile_kwargs=transpile_kwargs)

    def to_json(self, result: Optional[Dict[str, Any]] = None, indent: int = 2) -> str:
        payload = result if result is not None else self._require_result()
        return json.dumps(payload, indent=indent)

    def save_json(self, output_path: str, result: Optional[Dict[str, Any]] = None, indent: int = 2) -> str:
        payload = result if result is not None else self._require_result()
        return save_json_file(output_path, payload, indent=indent)

    def export_gate_counts_csv(self, output_path: str, result: Optional[Dict[str, Any]] = None) -> str:
        """
        Exports a CSV file with columns: category, gate, count
        where category is one of: clifford, non_clifford, non_unitary
        """
        payload = result if result is not None else self._require_result()

        rows = []
        for category_name, counts in payload["gate_counts"].items():
            for gate_name, count in counts.items():
                rows.append([category_name, gate_name, int(count)])

        rows.sort(key=lambda x: (x[0], -x[2], x[1]))
        return write_csv_file(output_path, ["category", "gate", "count"], rows)

    def plot_class_totals(
        self,
        result: Optional[Dict[str, Any]] = None,
        chart_type: str = "bar",
        figsize: tuple = (8, 5),
    ):
        """
        Plots a bar or pie chart showing the total number of gates in each class 
        (clifford, non-clifford, non-unitary) based on the provided result or 
        the last estimated result if not provided.
        """
        payload = result if result is not None else self._require_result()
        names = ["Clifford", "Non-Clifford", "Non-Unitary"]
        counts = [
            payload["totals"]["clifford"],
            payload["totals"]["non_clifford"],
            payload["totals"]["non_unitary"],
        ]
        bar_colors = ["#4C78A8", "#F58518", "#54A24B"]
        return plot_bar_or_pie(
            names=names,
            counts=counts,
            chart_type=chart_type,
            title="Gate Class Totals",
            xlabel="Gate Class",
            legend_title="Gate Class",
            figsize=figsize,
            bar_colors=bar_colors,
        )

    def plot_gate_breakdown(
        self,
        result: Optional[Dict[str, Any]] = None,
        gate_group: str = "all",
        chart_type: str = "bar",
        top_k: Optional[int] = None,
        figsize: tuple = (11, 5),
    ):
        """
        Plots a bar or pie chart showing the breakdown of gates within a specified group
        (clifford, non_clifford, non_unitary, or all) based on the provided result or
        the last estimated result if not provided.
        
        If `top_k` is specified, only the top k gates by count will be shown.
        """
        payload = result if result is not None else self._require_result()

        if gate_group == "all":
            counts = dict(payload["raw_count_ops"])
        elif gate_group in payload["gate_counts"]:
            counts = dict(payload["gate_counts"][gate_group])
        else:
            raise ValueError("gate_group must be one of: all, clifford, non_clifford, non_unitary")

        if not counts:
            raise ValueError(f"No gate data available for gate_group='{gate_group}'.")

        items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if top_k is not None and top_k > 0:
            items = items[:top_k]

        names, values = zip(*items)
        title_group = {
            "all": "All",
            "clifford": "Clifford",
            "non_clifford": "Non-Clifford",
            "non_unitary": "Non-Unitary",
        }.get(gate_group, gate_group)

        return plot_bar_or_pie(
            names=names,
            counts=values,
            chart_type=chart_type,
            title=f"Gate Breakdown ({title_group})",
            xlabel="Gate Type",
            legend_title="Gate",
            figsize=figsize,
        )

    def _require_result(self) -> Dict[str, Any]:
        if self.last_result is None:
            raise ValueError("No result available. Run estimate_circuit(...) first.")
        return self.last_result
