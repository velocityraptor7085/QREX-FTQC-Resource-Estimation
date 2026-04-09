from __future__ import annotations

from io import StringIO
from pathlib import Path
import json
import subprocess

import matplotlib.pyplot as plt
import pandas as pd

from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import PauliEvolutionGate, QFTGate
from qiskit.quantum_info import SparseObservable, get_clifford_gate_names
from qiskit.transpiler.passes import LitinskiTransformation, RemoveBarriers

from utils import iter_qiskit_pbc_circuit

'''
SOME STEPS FOR INSTALLATION AND INTEGRATION WITH THE BICYCLE COMPILER:
Prerequisites:
    - Git installed
    - rustup installed (https://rustup.rs/)
    - Python 3.8+ installed
    - Qiskit installed (pip install qiskit)

1. Clone the Repository (in Users/drarc):
    ```
    git clone https://github.com/qiskit-community/bicycle-architecture-compiler.git
    cd bicycle-architecture-compiler
    ```
2. Build the Binaries with Internal Gridsynth: Build the Rust workspace in release mode, 
   activating the `rsgridsynth` feature so that all arbitrary angle rotations can be synthesized 
   using native Rust code without external dependencies.
   ```
   cargo build --release -F rsgridsynth
   ```
   [from the root of the repo, where Cargo.toml is located]

3. Locate the Compiled Binaries: Once compilation is done, the executables will be located in the `target\release folder`. 
   The primary binaries you need are:
        - `bicycle_compiler.exe`
        - `bicycle_numerics.exe`
    [You can either add it globally to environment PATH or copy-paste these binaries in a directory within your workspace]
    Note: For the current implementation, copy-paste the binaries into the `bicycle_compiler_binaries` directory (for example, 
	this repository has the executables compiled for Windows 64-bit saved in the directory).

4. Generate the Measurement Tables (One-time Setup): The compiler relies on pre-generated measurement tables for optimization. 
   You should generate these to a dedicated folder that your Python script will know about.
    ```
    .\bicycle_compiler gross generate table_gross.dat
    .\bicycle_compiler two-gross generate table_two-gross.dat
    ```
    [You should run these after `cd` to the directory of the executables]
    [You should take these generated `.dat` tables and place them into a directory within your workspace]

5. Run this code
'''

class BicycleBackendIntegration:
	"""
	End-to-end integration wrapper around Bicycle compiler binaries.
	(You can install it from https://github.com/qiskit-community/bicycle-architecture-compiler/).

	Pipeline:
	1) Qiskit circuit -> PBC circuit (Litinski transformation)
	2) PBC JSON stream -> bicycle_compiler
	3) Compiler ISA stream -> bicycle_numerics
	4) CSV output -> pandas DataFrame
	"""

	def __init__(
		self,
		code_type: str = "gross",
		table_path: str = "measurement_tables/table_gross.dat",
		bin_dir: str = "bicycle_compiler_binaries",
	):
		self.code_type = code_type
		self.table_path = Path(table_path)
		self.bin_dir = Path(bin_dir)

	def qiskit_to_pbc(self, circuit: QuantumCircuit) -> str:
		"""
		Convert an arbitrary Qiskit circuit into line-delimited PBC JSON (expected format for the bicycle compiler).
		"""
		basis_gates = ["rz", "t", "tdg"] + get_clifford_gate_names()
		transpiled = transpile(circuit, basis_gates=basis_gates)
		pbc_circuit = LitinskiTransformation(fix_clifford=False)(transpiled)

		pbc_iter = iter_qiskit_pbc_circuit(pbc_circuit)
		return "\n".join(json.dumps(inst, separators=(",", ":")) for inst in pbc_iter)

	def run_bicycle_compiler(self, pbc_json_stream: str) -> str:
		"""
		Run bicycle_compiler on a PBC JSON stream.
		"""
		executable_path = self.bin_dir / "bicycle_compiler.exe"
		cmd = [
			str(executable_path),
			self.code_type,
			"--measurement-table",
			str(self.table_path),
		]

		result = subprocess.run(
			cmd,
			input=pbc_json_stream,
			text=True,
			capture_output=True,
			check=True,
		)
		return result.stdout

	def run_bicycle_numerics(
		self,
		compiled_isa_stream: str,
		num_qubits: int,
		noise_level: str = "1e-4",
	) -> str:
		"""
		Run bicycle_numerics and return CSV output as text.
		"""
		executable_path = self.bin_dir / "bicycle_numerics.exe"
		cmd = [str(executable_path), str(num_qubits), f"{self.code_type}_{noise_level}"]

		result = subprocess.run(
			cmd,
			input=compiled_isa_stream,
			text=True,
			capture_output=True,
			check=True,
		)
		return result.stdout

	def benchmark_circuit(self, circuit: QuantumCircuit, noise_level: str = "1e-4") -> pd.DataFrame:
		"""
		Run the full backend benchmark pipeline and return the parsed table.
		"""
		pbc_json_stream = self.qiskit_to_pbc(circuit) # 1. Get the PBC JSON stream from the Qiskit circuit
		compiled_isa_stream = self.run_bicycle_compiler(pbc_json_stream) # 2. Compile the PBC JSON stream to an ISA stream using the `bicycle_compiler` binary
		numerics_csv_stream = self.run_bicycle_numerics(compiled_isa_stream, circuit.num_qubits, noise_level)  # 3. Run the ISA stream through the `bicycle_numerics` binary to get a CSV stream of results
		return pd.read_csv(StringIO(numerics_csv_stream)) # 4. Return the results as a pandas DataFrame

	def visualize_benchmarks(
		self,
		df: pd.DataFrame,
		title: str = "Accumulated Logical Error vs Measurement Depth",
		output_path: str | None = None,
		show: bool = False,
	) -> None:
		"""
		Plot benchmark output using measurement_depth vs total_error.
		"""
		fig, ax = plt.subplots(figsize=(10, 6))
		ax.plot(df["measurement_depth"], df["total_error"], marker="o")
		ax.set_title(title)
		ax.set_xlabel("Measurement Depth")
		ax.set_ylabel("Total Error")
		ax.grid(True)

		if output_path:
			fig.savefig(output_path, dpi=300, bbox_inches="tight")
		if show:
			plt.show()

		plt.close(fig)

