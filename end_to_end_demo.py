from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import matplotlib.pyplot as plt

from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import PauliEvolutionGate, QFTGate, UnitaryGate
from qiskit.quantum_info import SparseObservable, get_clifford_gate_names
from qiskit.transpiler.passes import LitinskiTransformation, RemoveBarriers

from utils import ensure_directory, save_json_file, write_csv_file


ROOT = Path(__file__).resolve().parent
OUT_ROOT = ROOT / "example-outputs"

from algorithmic_level import HierarchicalResourceEstimator
from logical_level import LogicalResourceEstimator
from pbc_level import PBCResourceEstimator
from backend_integration import BicycleBackendIntegration


def _u3_matrix(theta: float, phi: float, lam: float) -> np.ndarray:
    """
    Returns a unitary matrix as a `np.ndarray` corresponding to the U3 gate with the given parameters.
    """
    return np.array(
        [
            [np.cos(theta / 2), -np.exp(1j * lam) * np.sin(theta / 2)],
            [np.exp(1j * phi) * np.sin(theta / 2), np.exp(1j * (phi + lam)) * np.cos(theta / 2)],
        ],
        dtype=complex,
    )

# Demo circuit 1 for the algorithmic level
def build_algorithmic_demo_circuit() -> QuantumCircuit:
    qft = QFTGate(3)
    qc = QuantumCircuit(4, name="example_circuit")
    qc.h(0)
    qc.cx(0, 1)
    qc.append(qft, [1, 2, 3])
    qc.measure_all()
    return qc

# Demo circuit 2 for the algorithmic level (showcasing control flow)
def build_algorithmic_demo_circuit_with_control_flow() -> QuantumCircuit:
    qft = QFTGate(3)
    qc_control = QuantumCircuit(4, 1, name="example_circuit_control_flow")
    qc_control.h(0)
    qc_control.cx(0, 1)
    qc_control.append(qft, [1, 2, 3])
    qc_control.measure(0, 0)
    with qc_control.if_test((qc_control.clbits[0], 0)):
        qc_control.h(2)
        qc_control.cx(2, 3)
    qc_control.measure_all()
    return qc_control

# Demo circuit for the logical level
def build_logical_demo_circuit() -> QuantumCircuit:
    qc = QuantumCircuit(3, name="logical_demo")
    qc.h(0)
    qc.cx(0, 1)
    qc.cz(1, 2)
    qc.append(UnitaryGate(_u3_matrix(0.92, 0.7, 0.4), label="u1"), [0])
    qc.append(UnitaryGate(_u3_matrix(1.31, 0.9, 0.2), label="u2"), [2])
    return qc

# Demo circuit for the PBC level (also used as the first circuit in the backend integration demo)
# CREDIT: https://github.com/qiskit-community/bicycle-architecture-compiler/blob/main/scripts/qiskit_demo.py
def build_pbc_demo_circuit(num_qubits: int, reps: int) -> QuantumCircuit:
	"""
    Build a Pauli evolution + measurement circuit used in backend tests.
    """
	observable = SparseObservable.from_sparse_list(
		[
			(interaction, [i, i + 1], -1)
			for interaction in ("XX", "YY", "ZZ")
			for i in range(num_qubits - 1)
		]
		+ [("Z", [i], 0.5) for i in range(num_qubits)],
		num_qubits=num_qubits,
	)
	evolution = PauliEvolutionGate(observable, time=1 / reps)

	circuit = QuantumCircuit(num_qubits, num_qubits, name="backend_evolution_demo")
	for _ in range(reps):
		circuit.append(evolution, circuit.qubits)
	for i in range(num_qubits):
		circuit.measure(i, i)
	return circuit

# Demo circuit 2 for the backend integration level (QFT circuit)
def build_backend_demo_circuit_qft(num_qubits: int) -> QuantumCircuit:
	"""
    Build a QFT circuit with measurements and barriers removed.
    """
	circuit = QuantumCircuit(num_qubits, name="backend_qft_demo")
	circuit.append(QFTGate(num_qubits), range(num_qubits))
	circuit.measure_all()

	# Litinski transformation expects circuits without barriers.
	return RemoveBarriers()(circuit)

# Function to transpile to the Clifford + T/Tdg basis
def transpile_clifford_t(circuit: QuantumCircuit, method: str, epsilon: float) -> QuantumCircuit:
    basis_gates = get_clifford_gate_names() + ["t", "tdg"]
    return transpile(
        circuit,
        basis_gates=basis_gates,
        optimization_level=2,
        unitary_synthesis_method=method,
        unitary_synthesis_plugin_config={"epsilon": epsilon},
    )

# Function to transpile to the Clifford + \psi (rz) basis
def transpile_clifford_rz(circuit: QuantumCircuit, method: str, epsilon: float) -> QuantumCircuit:
    basis_gates = get_clifford_gate_names() + ["rz", "t", "tdg"]
    return transpile(
        circuit,
        basis_gates=basis_gates,
        optimization_level=2,
        unitary_synthesis_method=method,
        unitary_synthesis_plugin_config={"epsilon": epsilon},
    )

# Compiles a circuit to a PBC circuit using the LitinskiTransformation pass
def compile_to_pbc(circuit: QuantumCircuit):
    basis = ["rz", "t", "tdg"] + get_clifford_gate_names()
    transpiled = transpile(circuit, basis_gates=basis)
    lit = LitinskiTransformation(fix_clifford=False)
    return lit(transpiled)


def run_algorithmic_demo() -> None:
    out_dir = Path(ensure_directory(str(OUT_ROOT / "algorithmic-level")))

    # Create a regular and control flow circuit
    qc = build_algorithmic_demo_circuit()
    qc_control = build_algorithmic_demo_circuit_with_control_flow()

    # Initialize the algorithmic level HierarchicalResourceEstimators
    estimator = HierarchicalResourceEstimator()
    estimator_control = HierarchicalResourceEstimator()

    # Estimate the circuit resources (at the algorithmic level)
    main_tree = estimator.estimate(qc)
    control_tree = estimator_control.estimate(qc_control)

    # Save the JSON representations of the resource trees
    save_json_file(str(out_dir / "algorithmic_main_tree.json"), main_tree)
    save_json_file(str(out_dir / "algorithmic_control_tree.json"), control_tree)

    # Save the textual visualizations of the resource trees
    estimator.save_tree_visualization("text", str(out_dir / "resource_tree_main.txt"))
    estimator_control.save_tree_visualization("text", str(out_dir / "resource_tree_control.txt"))

    # Export the resource costs as CSV files
    estimator.export_table_csv(str(out_dir / "resource_table_composite.csv"), abstraction_level="composite") # Original circuit  at composite abstration level
    estimator.export_table_csv(str(out_dir / "resource_table_depth1.csv"), tree_depth=1) # Original circuit at tree depth 1
    estimator_control.export_table_csv(str(out_dir / "resource_table_control_primitive.csv"), abstraction_level="primitive") # Control flow circuit at primitive abstraction level

    # Save the both resource tree visualizations in graphviz and pydot formats
    for fmt, filename in [
        ("graphviz", "resource_tree_graphviz.png"),
        ("pydot", "resource_tree_pydot.png"),
    ]:
        try:
            estimator.save_tree_visualization(fmt, str(out_dir / filename))
        except Exception:
            pass
    for fmt, filename in [
        ("graphviz", "resource_tree_cf_graphviz.png"),
        ("pydot", "resource_tree_cf_pydot.png"),
    ]:
        try:
            estimator_control.save_tree_visualization(fmt, str(out_dir / filename))
        except Exception:
            pass

    # Draw the circuits and their recursive decompositions in Qiskit (to see and validate how the hierarchical resource tree maps to the actual circuit)
    for prefix, circuit in [("original", qc), ("decomposed", qc.decompose()), ("double_decomposed", qc.decompose().decompose())]:
        try:
            circuit.draw(output="mpl", filename=str(out_dir / f"circuit_{prefix}.png"))
        except Exception:
            pass
    for prefix, circuit in [("control_flow", qc_control), ("control_flow_decomposed", qc_control.decompose())]:
        try:
            circuit.draw(output="mpl", filename=str(out_dir / f"circuit_{prefix}.png"))
        except Exception:
            pass

    # Generate a variety of breakdown charts for the original and control flow circuits at different levels of abstraction and tree depth
    chart_cases = [
        {"chart_type": "bar", "name": "primitives_bar"},
        {"chart_type": "pie", "name": "primitives_pie"},
        {"abstraction_level": "composite", "chart_type": "bar", "name": "composite_bar"},
        {"abstraction_level": "composite", "chart_type": "pie", "name": "composite_pie"},
        {"abstraction_level": "composite", "chart_type": "bar", "routine_metric": "total_ops", "name": "composite_bar_total_ops"},
        {"abstraction_level": "composite", "chart_type": "pie", "routine_metric": "total_ops", "name": "composite_pie_total_ops"},
        {"tree_depth": 0, "chart_type": "bar", "name": "depth0_bar"},
        {"tree_depth": 0, "chart_type": "pie", "name": "depth0_pie"},
        {"tree_depth": 1, "chart_type": "bar", "name": "depth1_bar"},
        {"tree_depth": 1, "chart_type": "pie", "name": "depth1_pie"},
        {"tree_depth": 1, "chart_type": "bar", "routine_metric": "total_ops", "name": "depth1_bar_total_ops"},
        {"tree_depth": 1, "chart_type": "pie", "routine_metric": "total_ops", "name": "depth1_pie_total_ops"},
    ]

    for case in chart_cases:
        params = {k: v for k, v in case.items() if k not in {"name"}}
        try:
            fig = estimator.visualize_gate_counts(**params)
            fig.savefig(out_dir / f"chart_{case['name']}.png", bbox_inches="tight")
            plt.close(fig)
        except Exception:
            pass

    for chart_type in ["bar", "pie"]:
        try:
            fig = estimator_control.visualize_gate_counts(chart_type=chart_type)
            fig.savefig(out_dir / f"chart_cf_primitives_{chart_type}.png", bbox_inches="tight")
            plt.close(fig)
        except Exception:
            pass


def run_logical_demo() -> None:
    out_dir = Path(ensure_directory(str(OUT_ROOT / "logical-level")))

    # Instantiate a Logical level resource estimator and simple circuit
    estimator = LogicalResourceEstimator()
    base_circuit = build_logical_demo_circuit()

    # Perform transpilation into Clifford+T/Tdg and Clifford+Rz bases at various epsilon values estimate resources, and save results and visualizations for each case
    epsilons = [1e-6, 1e-7, 1e-8]
    methods = ["gridsynth"]
    comparison_rows = []
    comparison_rows_rz = []

    for method in methods:
        method_failed = False
        for epsilon in epsilons:
            if method_failed:
                comparison_rows.append([method, epsilon, "SKIPPED_AFTER_FAILURE", "", "", ""]) 
                comparison_rows_rz.append([method, epsilon, "SKIPPED_AFTER_FAILURE", "", "", ""]) 
                continue

            try:
                transpiled = transpile_clifford_t(base_circuit, method=method, epsilon=epsilon) # Clifford + T/Tdg
                transpiled_rz = transpile_clifford_rz(base_circuit, method=method, epsilon=epsilon) # Clifford + Rz

                result = estimator.estimate(transpiled) # Estimate logical resources for the Clifford + T/Tdg version of the circuit
                result_rz = estimator.estimate(transpiled_rz) # Estimate logical resources for the Clifford + Rz version of the circuit

                # Save the results for both cases
                comparison_rows.append(
                    [
                        method,
                        epsilon,
                        result["circuit"]["depth"],
                        result["circuit"]["size"],
                        result["totals"]["clifford"],
                        result["totals"]["non_clifford"],
                        result["totals"]["t_like"],
                    ]
                )
                comparison_rows_rz.append(
                    [
                        method,
                        epsilon,
                        result_rz["circuit"]["depth"],
                        result_rz["circuit"]["size"],
                        result_rz["totals"]["clifford"],
                        result_rz["totals"]["non_clifford"],
                        result_rz["totals"]["t_like"],
                    ]
                )

                # Save results as JSON and CSV file formats
                tag = f"{method}_eps_{epsilon:.0e}".replace("-", "m")
                estimator.save_json(str(out_dir / f"logical_{tag}_counts.json"), result)
                estimator.export_gate_counts_csv(str(out_dir / f"logical_{tag}_counts.csv"), result)
                estimator.save_json(str(out_dir / f"logical_{tag}_counts_rz.json"), result_rz)
                estimator.export_gate_counts_csv(str(out_dir / f"logical_{tag}_counts_rz.csv"), result_rz)

                # Save visualizations of logical gate count class totals for both cases
                fig_class_bar = estimator.plot_class_totals(result, chart_type="bar")
                fig_class_pie = estimator.plot_class_totals(result, chart_type="pie")
                fig_class_bar.savefig(out_dir / f"logical_{tag}_class_totals_bar.png", bbox_inches="tight")
                fig_class_pie.savefig(out_dir / f"logical_{tag}_class_totals_pie.png", bbox_inches="tight")
                plt.close(fig_class_bar)
                plt.close(fig_class_pie)
                fig_class_bar_rz = estimator.plot_class_totals(result_rz, chart_type="bar")
                fig_class_pie_rz = estimator.plot_class_totals(result_rz, chart_type="pie")
                fig_class_bar_rz.savefig(out_dir / f"logical_{tag}_rz_class_totals_bar.png", bbox_inches="tight")
                fig_class_pie_rz.savefig(out_dir / f"logical_{tag}_rz_class_totals_pie.png", bbox_inches="tight")
                plt.close(fig_class_bar_rz)
                plt.close(fig_class_pie_rz)

                # Save visualizations of the logical gate breakdown by class for both cases
                for gate_group in ["clifford", "non_clifford", "non_unitary"]:
                    try:
                        fig_group_bar = estimator.plot_gate_breakdown(result, gate_group=gate_group, chart_type="bar", top_k=12)
                        fig_group_pie = estimator.plot_gate_breakdown(result, gate_group=gate_group, chart_type="pie", top_k=12)
                        fig_group_bar.savefig(out_dir / f"logical_{tag}_{gate_group}_breakdown_bar.png", bbox_inches="tight")
                        fig_group_pie.savefig(out_dir / f"logical_{tag}_{gate_group}_breakdown_pie.png", bbox_inches="tight")
                        plt.close(fig_group_bar)
                        plt.close(fig_group_pie)

                        fig_group_bar_rz = estimator.plot_gate_breakdown(result_rz, gate_group=gate_group, chart_type="bar", top_k=12)
                        fig_group_pie_rz = estimator.plot_gate_breakdown(result_rz, gate_group=gate_group, chart_type="pie", top_k=12)
                        fig_group_bar_rz.savefig(out_dir / f"logical_{tag}_rz_{gate_group}_breakdown_bar.png", bbox_inches="tight")
                        fig_group_pie_rz.savefig(out_dir / f"logical_{tag}_rz_{gate_group}_breakdown_pie.png", bbox_inches="tight")
                        plt.close(fig_group_bar_rz)
                        plt.close(fig_group_pie_rz)
                    except ValueError:
                        pass

            except Exception:
                method_failed = True
                comparison_rows.append([method, epsilon, "FAILED", "FAILED", "FAILED", "FAILED", "FAILED"])
                comparison_rows_rz.append([method, epsilon, "FAILED", "FAILED", "FAILED", "FAILED", "FAILED"])

    # Store the comparison table of results (using different gridsynth epsilon values) as a CSV file for both cases
    write_csv_file(
        str(out_dir / "logical_synthesis_comparison.csv"),
        ["method", "epsilon", "depth", "size", "clifford", "non_clifford", "t_like"],
        comparison_rows,
    )
    write_csv_file(
        str(out_dir / "logical_synthesis_comparison_rz.csv"),
        ["method", "epsilon", "depth", "size", "clifford", "non_clifford", "t_like"],
        comparison_rows_rz,
    )


def run_pbc_demo() -> None:
    out_dir = Path(ensure_directory(str(OUT_ROOT / "pbc-level")))

    # Perform PBC-level resource estimation
    estimator = PBCResourceEstimator()
    circuit = build_pbc_demo_circuit(num_qubits=10, reps=10) # Create a demo circuit
    pbc = compile_to_pbc(circuit) # Compile it to PBC form using the Litinski transformation pass
    result = estimator.estimate(pbc) # Estimate resources for the PBC circuit

    # Save results in JSON and CSV formats
    estimator.save_json(str(out_dir / "pbc_base_counts.json"), result)
    estimator.export_operation_counts_csv(str(out_dir / "pbc_base_counts.csv"), result)

    # Save visualizations of the PBC operation breakdown as bar and pie charts
    fig_bar = estimator.plot_operation_breakdown(result, chart_type="bar")
    fig_pie = estimator.plot_operation_breakdown(result, chart_type="pie")
    fig_bar.savefig(out_dir / "pbc_base_breakdown_bar.png", bbox_inches="tight")
    fig_pie.savefig(out_dir / "pbc_base_breakdown_pie.png", bbox_inches="tight")
    plt.close(fig_bar)
    plt.close(fig_pie)

    # Store the raw results in text format
    with open(out_dir / "pbc_results.txt", "w", encoding="utf-8") as f:
        f.write(json.dumps(result, indent=2))


def run_backend_demo() -> None:
    out_dir = Path(ensure_directory(str(OUT_ROOT / "backend-integration")))

    # Initialize the backend bicycle compiler wrapper
    backend = BicycleBackendIntegration(
        code_type="gross",
        table_path="measurement_tables/table_gross.dat",
        bin_dir="bicycle_compiler_binaries",
    )

    # Create and draw the demo circuits
    evolution_circuit = build_pbc_demo_circuit(num_qubits=5, reps=10)
    evolution_circuit.draw(output="mpl", filename=str(out_dir / "backend_evolution_circuit.png"))
    qft_circuit = build_backend_demo_circuit_qft(num_qubits=4)
    qft_circuit.draw(output="mpl", filename=str(out_dir / "backend_qft_circuit.png"))

    # Save PBC JSON streams for both circuits (as generated by the `qiskit_to_pbc` method) which is consumed by the bicycle compiler
    (out_dir / "backend_evolution_pbc.jsonl").write_text(backend.qiskit_to_pbc(evolution_circuit), encoding="utf-8")
    (out_dir / "backend_qft_pbc.jsonl").write_text(backend.qiskit_to_pbc(qft_circuit), encoding="utf-8")

    # Use the bicycle compiler to run numerics and benchmark both circuits
    try:
        # Benchmark both circuits and store the raw results as CSV files
        evolution_df = backend.benchmark_circuit(evolution_circuit, noise_level="1e-4")
        qft_df = backend.benchmark_circuit(qft_circuit, noise_level="1e-4")
        evolution_df.to_csv(out_dir / "backend_evolution_benchmark.csv", index=False)
        qft_df.to_csv(out_dir / "backend_qft_benchmark.csv", index=False)

        # Visualize the accumulated logical error vs measurement depth for both circuits
        backend.visualize_benchmarks(
            evolution_df,
            title="Evolution Circuit: Accumulated Logical Error vs Measurement Depth",
            output_path=str(out_dir / "backend_evolution_benchmark.png"),
        )
        backend.visualize_benchmarks(
            qft_df,
            title="QFT Circuit: Accumulated Logical Error vs Measurement Depth",
            output_path=str(out_dir / "backend_qft_benchmark.png"),
        )

    except Exception as exc:
        # Keep the rest of the demo runnable even when Bicycle binaries/tables are absent.
        status = (
            "Backend integration step could not be executed.\n"
            f"Reason: {type(exc).__name__}: {exc}\n\n"
            "Expected prerequisites:\n"
            "- bicycle_compiler_binaries/bicycle_compiler.exe\n"
            "- bicycle_compiler_binaries/bicycle_numerics.exe\n"
            "- measurement_tables/table_gross.dat\n"
        )
        (out_dir / "backend_status.txt").write_text(status, encoding="utf-8")


# Execute the end-to-end demo, which runs all the individual demos for each level and saves outputs to the `example-outputs` directory:
ensure_directory(str(OUT_ROOT))
run_algorithmic_demo()
run_logical_demo()
run_pbc_demo()
run_backend_demo()
print("Done. Outputs written to example-outputs/<algorithmic-level|logical-level|pbc-level|backend-integration>.")