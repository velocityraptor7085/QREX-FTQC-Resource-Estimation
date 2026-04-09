from __future__ import annotations

from collections.abc import Iterator
import csv
import json
import numpy as np
import os
from qiskit import QuantumCircuit
from typing import Any, Dict, List, Optional, Sequence, Tuple


def ensure_directory(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def save_json_file(output_path: str, payload: Dict[str, Any], indent: int = 2) -> str:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=indent)
    return output_path


def save_text_file(output_path: str, content: str) -> str:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def write_csv_file(output_path: str, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(list(headers))
        writer.writerows(rows)
    return output_path


def autopct_with_counts(values: Sequence[int]):
    total = sum(values)

    def _fmt(pct: float) -> str:
        if total == 0:
            return "0.0%\n(0)"
        count = int(round((pct / 100.0) * total))
        return f"{pct:.1f}%\n({count})"

    return _fmt


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError("matplotlib is required for visualization methods.") from exc
    return plt


def require_graphviz():
    try:
        import graphviz
    except ImportError as exc:
        raise ImportError("graphviz is required for graphviz visualization.") from exc
    return graphviz


def require_pydot():
    try:
        import pydot
    except ImportError as exc:
        raise ImportError("pydot is required for pydot visualization.") from exc
    return pydot


def plot_bar_or_pie(
    names: Sequence[str],
    counts: Sequence[int],
    chart_type: str,
    title: str,
    xlabel: str,
    legend_title: str,
    figsize: Tuple[int, int],
    bar_colors: Optional[Sequence[str]] = None,
):
    if not names or not counts:
        raise ValueError("No data available for plotting.")

    plt = require_matplotlib()
    normalized_chart = chart_type.strip().lower()
    fig, ax = plt.subplots(figsize=figsize)

    # Plot the bar graph:
    if normalized_chart == "bar":
        colors = bar_colors if bar_colors is not None else plt.cm.Set3(range(len(names)))
        bars = ax.bar(names, counts, color=colors, edgecolor="black", linewidth=1.3)
        peak = max(counts) if counts else 0
        offset = peak * 0.02 if peak > 0 else 0.1
        for i, value in enumerate(counts):
            ax.text(
                i,
                value + offset,
                str(int(value)),
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=9,
            )
        for bar in bars:
            bar.set_alpha(0.95)
        ax.set_ylabel("Count", fontweight="bold")
        ax.set_xlabel(xlabel, fontweight="bold")
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        if len(names) > 6:
            plt.xticks(rotation=45, ha="right")
    
    # Plot the pie chart:
    else:
        colors = plt.cm.Set3(range(len(names)))
        wedges, _, autotexts = ax.pie(
            counts,
            labels=None,
            autopct=autopct_with_counts(counts),
            colors=colors,
            startangle=90,
            wedgeprops=dict(edgecolor="black", linewidth=1.2),
        )
        for autotext in autotexts:
            autotext.set_fontsize(8)
            autotext.set_fontweight("bold")
        legend_labels = [f"{name} ({count})" for name, count in zip(names, counts)]
        ax.legend(wedges, legend_labels, title=legend_title, loc="center left", bbox_to_anchor=(1.0, 0.5))
        ax.axis("equal")

    ax.set_title(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def _tree_depth(node: Dict[str, Any]) -> int:
    children = node.get("children", [])
    if not children:
        return 1
    return 1 + max(_tree_depth(child) for child in children)


def build_ascii_tree(root: Dict[str, Any]) -> str:
    lines: List[str] = []

    def walk(node: Dict[str, Any], prefix: str, is_last: bool) -> None:
        total_ops = node.get("resources", {}).get("total", 0)
        level = node.get("abstraction_level", "unknown")
        label = f"{node.get('name', 'node')} ({node.get('type', 'Unknown')}) [{level}] - {total_ops} ops"
        connector = "+-- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{label}")

        child_prefix = prefix + ("    " if is_last else "|   ")
        children = sorted(node.get("children", []), key=lambda x: x.get("abstraction_depth", 0))
        for i, child in enumerate(children):
            walk(child, child_prefix, i == len(children) - 1)

    walk(root, "", True)
    return "\n".join(lines)


def build_graphviz_tree(root: Dict[str, Any], level_colors: Dict[str, str], engine: str = "dot"):
    graphviz = require_graphviz()
    dot = graphviz.Digraph(comment="Hierarchical Resource Tree", engine=engine)

    def walk(node: Dict[str, Any], node_id: str) -> None:
        total_ops = node.get("resources", {}).get("total", 0)
        level = node.get("abstraction_level", "unknown")
        label = f"{node.get('name', 'node')}\\n{node.get('type', 'Unknown')}\\n[{level}]\\n{total_ops} ops"
        color = level_colors.get(level, "lightgray")
        dot.node(node_id, label=label, style="filled", fillcolor=color, shape="box")

        for idx, child in enumerate(node.get("children", [])):
            child_id = f"{node_id}_{idx}"
            dot.edge(node_id, child_id)
            walk(child, child_id)

    walk(root, "root")
    return dot


def build_pydot_tree(root: Dict[str, Any], level_colors: Dict[str, str], engine: str = "dot"):
    pydot = require_pydot()
    graph = pydot.Dot(graph_type="digraph", rankdir="TB", graph_typeorder="graph", engine=engine)

    def walk(node: Dict[str, Any], node_id: str) -> None:
        total_ops = node.get("resources", {}).get("total", 0)
        level = node.get("abstraction_level", "unknown")
        label = f"{node.get('name', 'node')}\\n{node.get('type', 'Unknown')}\\n[{level}]\\n{total_ops} ops"
        color = level_colors.get(level, "lightgray")
        graph.add_node(pydot.Node(node_id, label=label, style="filled", fillcolor=color, shape="box"))

        for idx, child in enumerate(node.get("children", [])):
            child_id = f"{node_id}_{idx}"
            graph.add_edge(pydot.Edge(node_id, child_id))
            walk(child, child_id)

    walk(root, "root")
    return graph


def save_graphviz_render(dot: Any, output_path: str) -> str:
    base, ext = os.path.splitext(output_path)
    render_format = ext.lstrip(".") if ext else "png"
    return dot.render(base or output_path, format=render_format, cleanup=True)


def save_pydot_render(graph: Any, output_path: str) -> str:
    base, ext = os.path.splitext(output_path)
    render_format = ext.lstrip(".") if ext else "png"
    if render_format.lower() == "svg":
        graph.write_svg(output_path)
    else:
        graph.write(output_path, format=render_format)
    return output_path

# CREDIT: https://github.com/qiskit-community/bicycle-architecture-compiler/blob/main/scripts/qiskit_parser.py
# Copyright contributors to the Bicycle Architecture Compiler project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Qiskit circuit parser for bicycle compiler."""

PAULI_TABLE = {
    (True, True): "Y",
    (True, False): "Z",
    (False, True): "X",
    (False, False): "I",
}


def iter_qiskit_pbc_circuit(
    pbc: "QuantumCircuit", as_str: bool = False
) -> Iterator[dict] | Iterator[str]:
    """Yield PBC instructions consumable by the bicycle compiler.

    Args:
        pbc: The Qiskit ``QuantumCircuit`` object to iterate over. This circuit is required to
            be in PBC format, i.e. contain only ``PauliEvolutionGate`` objects with a single
            Pauli as operator, and ``PauliProductMeasurement`` instructions.
        as_str: If ``True``, yield instructions as string that's directly consumable by
            the ``bicycle_compiler`` executable. If ``False``, return the plain dictionary.

    Returns:
        An iterator over PBC instructions in the bicycle compilers JSON format, that is
        ``{"Rotation": {"basis": ["Z", "X", "Y", "I"], "angle": 0.123}}`` or
        ``{"Measurement": {"basis": ["Z", "X", "Y", "I"], "flipped": True}}``.
        If ``as_str`` is ``True``, the dictionaries are JSON serialized and whitespaces removed.

    Raises:
        ValueError: If the input circuit is not in the required PBC format.
    """

    qubit_to_index = {qubit: index for index, qubit in enumerate(pbc.qubits)}

    # potentially transform the instruction to string format
    if as_str:
        to_str = lambda inst: json.dumps(inst).replace(" ", "")
    else:
        to_str = lambda inst: inst  # no op

    for i, inst in enumerate(pbc.data):
        if inst.name == "PauliEvolution":
            evo = inst.operation
            if isinstance(evo.operator, list):
                raise ValueError("Grouped operators in Pauli not supported.")

            op = evo.operator.to_sparse_list()
            if len(op) > 1:
                raise ValueError("PauliEvolution is not a single rotation.")
            paulis, indices, coeff = op[0]

            basis = ["I"] * pbc.num_qubits
            for pauli, i in zip(paulis, indices):
                basis[i] = pauli

            angle = evo.params[0] * np.real(coeff)

            rot = {"Rotation": {"basis": basis, "angle": str(angle)}}
            yield to_str(rot)

        elif inst.name == "pauli_product_measurement":
            ppm = inst.operation

            # TODO Use a public interface, once available.
            # See also https://github.com/Qiskit/qiskit/issues/15468.
            z, x, phase = ppm._to_pauli_data()

            basis = ["I"] * pbc.num_qubits
            for qubit, zq, xq in zip(inst.qubits, z, x):
                basis[qubit_to_index[qubit]] = PAULI_TABLE[(zq, xq)]

            flipped = bool(phase == 2)
            meas = {"Measurement": {"basis": basis, "flip_result": flipped}}
            yield to_str(meas)

        else:
            raise ValueError(f"Unsupported instruction in PBC circuit: {inst.name}")