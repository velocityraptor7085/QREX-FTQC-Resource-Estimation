from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Union
import json

from qiskit.circuit import Instruction, QuantumCircuit
from qiskit.circuit.controlflow import ControlFlowOp

from utils import (
    build_ascii_tree,
    build_graphviz_tree,
    build_pydot_tree,
    plot_bar_or_pie,
    save_graphviz_render,
    save_pydot_render,
    save_text_file,
    write_csv_file,
)


class HierarchicalResourceEstimator:
    """
    Algorithmic-level resource estimator that builds a hierarchical representation 
    of a quantum circuit. It recursively walks a circuit, builds a hierarchy of operations, 
    and then computes operation counts bottom-up.

    Semantics of the JSON resource tree fields:
        - `name`: The name of the operation or subroutine (e.g., "h", "cx", "my_composite_op").
        - `type`: The type of the operation (e.g., "Instruction", "QuantumCircuit", "ControlFlowOp").
        - `num_qubits`: The number of qubits that the operation acts on.
        - `num_clbits`: The number of classical bits that the operation acts on.
        - `params`: Any parameters associated with the operation (e.g., rotation angles).
        - `resources`: A dictionary containing the total count of primitive operations (gates) under this node, including a "total" count and counts for each specific gate type.
        - `children`: A list of child nodes representing sub-operations or blocks within control flow operations
        - `abstraction_level`: A string indicating the abstraction level of the node (e.g., "algorithmic", "control_flow", "composite", "primitive").
        - `abstraction_depth`: An integer representing the depth of the node in the abstraction hierarchy (0 for the root, increasing as we go down the tree).
    """

    def __init__(self):
        self.resource_tree: Dict[str, Any] = {}
        self.abstraction_hierarchy = {
            "algorithmic": 0,
            "control_flow": 1,
            "control_flow_block": 2,
            "composite": 3,
            "primitive": 4,
        }
        self.level_colors = {
            "algorithmic": "lightcoral",
            "control_flow": "lightblue",
            "control_flow_block": "lightgreen",
            "composite": "orange",
            "primitive": "plum",
        }

    def estimate_circuit(self, circuit: QuantumCircuit, max_depth: int = 10) -> Dict[str, Any]:
        # Define the root node (corresponding to the entire quantum algorithm circuit)
        root = {
            "name": circuit.name or "main_circuit",
            "type": "QuantumCircuit",
            "num_qubits": circuit.num_qubits,
            "num_clbits": circuit.num_clbits,
            "resources": {},
            "children": [],
            "abstraction_level": "algorithmic",
            "abstraction_depth": 0,
        }

        # Returns a dictionary representation of a primitive (leaf) operation node
        def primitive_node(operation: Instruction) -> Dict[str, Any]:
            return {
                "name": operation.name,
                "type": type(operation).__name__,
                "num_qubits": operation.num_qubits,
                "num_clbits": operation.num_clbits,
                "params": getattr(operation, "params", []),
                "resources": {"total": 1, operation.name: 1},
                "children": [],
                "abstraction_level": "primitive",
                "abstraction_depth": self.abstraction_hierarchy["primitive"],
            }

        # Recursive function to walk the circuit and build the hierarchical tree
        def walk(current_circuit: QuantumCircuit, parent: Dict[str, Any], depth: int) -> None:
            # Recursively walk the circuit upto the max_depth or until we reach primitive (leaf) nodes
            if depth >= max_depth:
                return

            # Iterate through all the instructions in the current circuit
            for instruction in current_circuit.data:
                operation = instruction.operation

                # 1. Control flow operations:
                if isinstance(operation, ControlFlowOp):
                    cf_node = {
                        "name": operation.name,
                        "type": "ControlFlowOp",
                        "num_qubits": operation.num_qubits,
                        "num_clbits": operation.num_clbits,
                        "resources": {},
                        "children": [],
                        "abstraction_level": "control_flow",
                        "abstraction_depth": self.abstraction_hierarchy["control_flow"],
                    }

                    # Evaluate the blocks within a control flow operation
                    for index, block in enumerate(operation.blocks):
                        block_node = {
                            "name": f"{operation.name}_block_{index}",
                            "type": "QuantumCircuit",
                            "num_qubits": block.num_qubits,
                            "num_clbits": block.num_clbits,
                            "resources": {},
                            "children": [],
                            "abstraction_level": "control_flow_block",
                            "abstraction_depth": self.abstraction_hierarchy["control_flow_block"],
                        }
                        walk(block, block_node, depth + 1)
                        cf_node["children"].append(block_node)

                    parent["children"].append(cf_node)
                    continue

                # 2. Other composite (non-primitive) operations:
                if hasattr(operation, "definition") and operation.definition is not None:
                    comp_node = {
                        "name": operation.name,
                        "type": type(operation).__name__,
                        "num_qubits": operation.num_qubits,
                        "num_clbits": operation.num_clbits,
                        "params": getattr(operation, "params", []),
                        "resources": {},
                        "children": [],
                        "abstraction_level": "composite",
                        "abstraction_depth": self.abstraction_hierarchy["composite"],
                    }
                    walk(operation.definition, comp_node, depth + 1) # Recursively walk the definition of the composite operation
                    parent["children"].append(comp_node)
                    continue

                # 3. Primitive operations (leaf nodes):
                parent["children"].append(primitive_node(operation))

        # Bottom-up aggregation of resource counts for each node in the tree
        def aggregate(node: Dict[str, Any]) -> Dict[str, int]:
            children = node.get("children", [])
            if not children:
                return node["resources"]

            merged: Dict[str, int] = {}
            for child in children:
                child_resources = aggregate(child)
                for gate_name, count in child_resources.items():
                    merged[gate_name] = merged.get(gate_name, 0) + count
            node["resources"] = merged
            return merged

        walk(circuit, root, depth=0)
        aggregate(root)
        self.resource_tree = root
        return root

    def estimate(self, circuit: QuantumCircuit, **kwargs) -> Dict[str, Any]:
        # Just to have a consistent API name with estimators at other levels
        return self.estimate_circuit(circuit, **kwargs)

    def to_json(self) -> str:
        return json.dumps(self.resource_tree, indent=2)

    def get_abstraction_layers(self) -> List[str]:
        layers = set()

        # Simple logic to get a list of abstraction layers present in the tree, ordered by hierarchy
        def walk(node: Dict[str, Any]) -> None:
            level = node.get("abstraction_level")
            if level is not None:
                layers.add(level)
            for child in node.get("children", []):
                walk(child)

        walk(self.resource_tree)
        return sorted(layers, key=lambda x: self.abstraction_hierarchy.get(x, 999))

    def to_table(self, abstraction_level: Optional[str] = None, tree_depth: Optional[int] = None) -> str:
        """
        Generates a text-based table representation of the resource tree, filtered by 
        abstraction level or tree depth.
        """

        rows = self._table_rows(abstraction_level=abstraction_level, tree_depth=tree_depth)
        if not rows:
            if tree_depth is not None:
                return f"No data found for the specified filter (tree_depth={tree_depth})."
            return f"No data found for the specified filter (abstraction_level={abstraction_level})."

        gate_names = self._all_gate_names(rows)
        headers = ["Name", "Type", "Qubits", "Clbits", "Occurrences", "Total Ops", "Abs Level", *gate_names]

        display_rows: List[List[str]] = []
        for item in rows:
            data = [
                item["name"],
                item["type"],
                str(item["num_qubits"]),
                str(item["num_clbits"]),
                str(item["occurrences"]),
                str(item["resources"].get("total", 0)),
                item["abstraction_level"],
            ]
            for gate_name in gate_names:
                data.append(str(item["resources"].get(gate_name, 0)))
            display_rows.append(data)

        col_widths = []
        for idx, header in enumerate(headers):
            widest = len(header)
            for row in display_rows:
                widest = max(widest, len(row[idx]))
            col_widths.append(widest)

        header_line = "  ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers))
        sep_line = "  ".join("-" * w for w in col_widths)
        table_lines = [header_line, sep_line]
        for row in display_rows:
            table_lines.append("  ".join(f"{value:<{col_widths[i]}}" for i, value in enumerate(row)))
        return "\n".join(table_lines)

    def export_table_csv(
        self,
        output_path: str,
        abstraction_level: Optional[str] = None,
        tree_depth: Optional[int] = None,
    ) -> str:
        """
        Similar to `to_table`, but exports the data as a CSV file to the specified output path,
        filtered by abstraction level or tree depth.
        """

        rows = self._table_rows(abstraction_level=abstraction_level, tree_depth=tree_depth)
        if not rows:
            if tree_depth is not None:
                raise ValueError(f"No data found for the specified filter (tree_depth={tree_depth}).")
            raise ValueError(f"No data found for the specified filter (abstraction_level={abstraction_level}).")

        gate_names = self._all_gate_names(rows)
        headers = ["Name", "Type", "Qubits", "Clbits", "Occurrences", "Total Ops", "Abs Level", *gate_names]

        csv_rows: List[List[Any]] = []
        for item in rows:
            values: List[Any] = [
                item["name"],
                item["type"],
                item["num_qubits"],
                item["num_clbits"],
                item["occurrences"],
                item["resources"].get("total", 0),
                item["abstraction_level"],
            ]
            for gate_name in gate_names:
                values.append(item["resources"].get(gate_name, 0))
            csv_rows.append(values)

        return write_csv_file(output_path, headers, csv_rows)

    def to_tree_visualization(self, format: str = "text", **kwargs) -> Union[str, Any]:
        if format == "text":
            return build_ascii_tree(self.resource_tree)
        if format == "graphviz":
            return build_graphviz_tree(self.resource_tree, self.level_colors, **kwargs)
        if format == "pydot":
            return build_pydot_tree(self.resource_tree, self.level_colors, **kwargs)
        raise ValueError(f"Unsupported format: {format}")

    def save_tree_visualization(self, format: str, output_path: str, **kwargs) -> str:
        if format == "text":
            return save_text_file(output_path, self.to_tree_visualization("text"))
        if format == "graphviz":
            dot = self.to_tree_visualization("graphviz", **kwargs)
            return save_graphviz_render(dot, output_path)
        if format == "pydot":
            graph = self.to_tree_visualization("pydot", **kwargs)
            return save_pydot_render(graph, output_path)
        raise ValueError(f"Unsupported format for saving: {format}")

    def visualize_gate_counts(
        self,
        abstraction_level: Optional[str] = None,
        tree_depth: Optional[int] = None,
        chart_type: str = "bar",
        routine_metric: str = "occurrences",
        figsize=(12, 6),
    ):
        """
        Visualizes the subroutine resource counts as a bar or pie chart, 
        filtered by abstraction level or tree depth.
        There is an option to visualize either the total operation counts 
        or the number of occurrences of each routine.
        """
        is_primitive_view = abstraction_level is None or abstraction_level == "primitive"

        if not is_primitive_view or tree_depth is not None:
            if routine_metric == "total_ops":
                counts = self._routine_resource_costs(target_level=abstraction_level, target_depth=tree_depth) # Counting the total number of operations
            else:
                counts = self._routine_occurrences(target_level=abstraction_level, target_depth=tree_depth) # Counting the number of occurrences of each routine
            if not counts:
                raise ValueError("No routine data found for the specified filter.")
            names, values = zip(*sorted(counts.items(), key=lambda x: x[1], reverse=True))
            xlabel = "Routine Type"
        
        # For the primitive view, we want to visualize the counts of individual gates/operations rather than subroutines
        else:
            gate_counts: Dict[str, int] = defaultdict(int)
            self._aggregate_gate_counts(self.resource_tree, gate_counts, abstraction_level)
            gate_counts.pop("total", None)
            if not gate_counts:
                raise ValueError("No gate data found for the specified filter.")
            names, values = zip(*sorted(gate_counts.items(), key=lambda x: x[1], reverse=True))
            xlabel = "Gate Type"

        if tree_depth is not None:
            title = f"Gate/Operation Counts (Tree Depth {tree_depth})"
        elif abstraction_level is not None:
            title = f"Gate/Operation Counts ({abstraction_level.capitalize()} Level)"
        else:
            title = "Gate/Operation Counts (All Primitives)"

        return plot_bar_or_pie(
            names=names,
            counts=values,
            chart_type=chart_type,
            title=title,
            xlabel=xlabel,
            legend_title=xlabel,
            figsize=figsize,
        )

    def _table_rows(self, abstraction_level: Optional[str], tree_depth: Optional[int]) -> List[Dict[str, Any]]:
        """
        Generates a list of rows for a table representation of the resource tree, 
        filtered by abstraction level or tree depth.
        """
        selected: List[Dict[str, Any]] = []

        # Walk the tree and select nodes that match the specified abstraction level or tree depth
        def walk(node: Dict[str, Any], depth: int) -> None:
            matches_depth = tree_depth is not None and depth == tree_depth
            matches_level = tree_depth is None and (
                abstraction_level is None or node.get("abstraction_level") == abstraction_level
            )
            if matches_depth or matches_level:
                selected.append(
                    {
                        "name": node["name"],
                        "type": node["type"],
                        "num_qubits": node["num_qubits"],
                        "num_clbits": node["num_clbits"],
                        "resources": dict(node.get("resources", {})),
                        "abstraction_depth": node.get("abstraction_depth", 0),
                        "abstraction_level": node.get("abstraction_level", "unknown"),
                    }
                )
            for child in node.get("children", []):
                walk(child, depth + 1)

        walk(self.resource_tree, 0)

        selected.sort(key=lambda x: x.get("abstraction_depth", 0))

        # De-duplicate rows by name, summing occurrences if there are multiple entries for the same routine
        deduplicated: Dict[str, Dict[str, Any]] = {}
        for item in selected:
            key = item["name"]
            if key not in deduplicated:
                item["occurrences"] = 1
                deduplicated[key] = item
            else:
                deduplicated[key]["occurrences"] += 1
        return list(deduplicated.values())

    @staticmethod
    def _all_gate_names(rows: List[Dict[str, Any]]) -> List[str]:
        gate_names = set()
        for item in rows:
            gate_names.update(item.get("resources", {}).keys())
        gate_names.discard("total")
        return sorted(gate_names)

    def _aggregate_gate_counts(
        self,
        node: Dict[str, Any],
        gate_counts: Dict[str, int],
        abstraction_level: Optional[str] = None,
    ) -> None:
        """
        Recursively walks the tree and aggregates gate counts for primitive nodes,
        filtered by abstraction level if specified.
        """
        if abstraction_level is None:
            if node.get("abstraction_level") == "primitive":
                for name, count in node.get("resources", {}).items():
                    gate_counts[name] += count
        else:
            if node.get("abstraction_level") == abstraction_level:
                for name, count in node.get("resources", {}).items():
                    gate_counts[name] += count

        for child in node.get("children", []):
            self._aggregate_gate_counts(child, gate_counts, abstraction_level)

    def _routine_occurrences(
        self,
        target_level: Optional[str] = None,
        target_depth: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Counts the occurrences of each routine in the resource tree, filtered by abstraction level or tree depth.
        """
        counts: Dict[str, int] = defaultdict(int)

        def walk(node: Dict[str, Any], depth: int) -> None:
            if target_depth is not None:
                # If we're filtering by tree depth, we only count nodes that are exactly at the target depth
                if depth == target_depth:
                    counts[node.get("name", "unknown")] += 1
            
            # If we're filtering by abstraction level, we count all nodes that match the target level (regardless of depth)
            elif target_level and node.get("abstraction_level") == target_level:
                counts[node.get("name", "unknown")] += 1

            for child in node.get("children", []):
                walk(child, depth + 1)

        walk(self.resource_tree, 0)
        return counts

    def _routine_resource_costs(
        self,
        target_level: Optional[str] = None,
        target_depth: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Similar to `_routine_occurrences`, but instead of counting occurrences, 
        it sums the total operation counts for each routine in the resource tree, 
        filtered by abstraction level or tree depth.
        """
        costs: Dict[str, int] = defaultdict(int)

        def walk(node: Dict[str, Any], depth: int) -> None:
            node_total = int(node.get("resources", {}).get("total", 0))
            if target_depth is not None:
                if depth == target_depth:
                    costs[node.get("name", "unknown")] += node_total
            elif target_level and node.get("abstraction_level") == target_level:
                costs[node.get("name", "unknown")] += node_total

            for child in node.get("children", []):
                walk(child, depth + 1)

        walk(self.resource_tree, 0)
        return costs
