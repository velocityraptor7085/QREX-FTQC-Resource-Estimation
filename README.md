# QREX (Quantum Resource EXplorer)
## An End-to-End Resource Estimation Tool for Fault-Tolerant Quantum Algorithms in Qiskit
<!-- QREX Logo -->
<p>
  <img width="1900" height="763" alt="Image" src="https://github.com/user-attachments/assets/0c1e0bf5-765b-42a1-b4bb-0e1d304551e5" />
</p>
This repository implements an end-to-end fault-tolerant resource estimation tool built on top of [Qiskit](https://github.com/Qiskit/qiskit) and the [Bicycle Architecture Compiler](https://github.com/qiskit-community/bicycle-architecture-compiler).

The core objective of this implementation is a focus on producing exact resource estimates for quantum algorithms (implemented as Qiskit `QuantumCircuit` objects) at various layers of the compilation pipeline to fault-tolerant architectures (such as [IBM's Gross Code](https://arxiv.org/abs/2506.03094) using schemes similar to that proposed in [A Game of Surface Codes](https://arxiv.org/abs/1808.02892)). 

This is achieved by integrating resource estimates and visualization tools coupled with the Qiskit transpiler at these different steps in the fault-toleratn compilation pipeline. These steps (as inspired by ) at can be summarized at a high level as:
1. **Algorithmic level** (implemented in `algorithmic_level.py`): 
  - Refers to the abstraction layer of the quantum algorithm (`QuantumCircuit` object) itself.
  - Here, hierarchical resource estimation trees are constructed and visualized to show the user a hierarchical composition of their algorithm into subroutines and relative operation cost breakdowns between them (this would help them assess the most costly subroutines at the algorithmic level, before actually compiling the circuit). This is inspired by the DAGs used in [Qualtran](https://arxiv.org/abs/2409.04643) for resource estimation.
2. **Logical level** (implemented in `logical_level.py`):
  - Refers to the logical gate operation level (in a fault-tolerant basis).
  - The Qiskit transpiler is used here to generate circuits in a suitable fault-tolerant basis set (such as `Clifford+T/Tdg` or `Clifford+Rz`). Based on this, the relative counts of Cliffords vs Non-Cliffords vs Non-Unitary operations in the circuit can be tabulated and visualized. Additionally, individual logical gate breakdowns can be analyzed as well.
3. **Pauli-Based Computation (PBC) level** (implemented in `pbc_level.py`):
  - Refers to the Pauli-based Computation level primitives (namely product pauli rotations (implemented a `PauliEvolutionGate` operations) and product pauli measurements (implemented as `PauliProductMeasurement` operations)). These are produced after applying the [`LitinskiTransformation` pass](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.2/qiskit.transpiler.passes.LitinskiTransformation) to a Clifford+Rz circuit.
  - The counts of these primitives can be visualized and counted in a similar manner to the Logical level.
4. **Physical level** (implemented in `backend-integration.py`):
  - Refers to the physical level resource estimates after compiling PBC circuits into a fault-tolerant quantum architecture (including quantum error correcting codes, magic state distillation overheads, etc.)
  - Relies on the Bicycle architecture compiler as a backend compiler. (The binaries need to be compiled from source following the instructions from the [GitHub repository](https://github.com/qiskit-community/bicycle-architecture-compiler)).

**Notes**: 
- Since the intent to keep QREX as a general, architecture-agnostic resource estimation tool, there are full implementations for levels 1,2 and 3 (Algorithmic, Logical and PBC levels). 
- We treat PBC as a suitable architecture-agnostic Intermediate Representation (IR) for Fault-Tolerant architectures..
- Hence we can think of QREX as resource estimation tied to a "front-end" of a quantum compiler toolchain, with architecture-specific backend compilers consuming a PBC IR and compiling to a specific hardware architecture backend (and potential estimating physical costs). Here, the bicycle compiler was chosen due to its existing open-source implementation as a proof of concept for backend integration in this implementation.

## Installaton + Running the Demo

### Prerequisites and Dependencies:
First, ensure that Git, [rustup](https://rustup.rs/) and Python 3.8+ are installed.
1. Python dependencies:
```bash
pip install -r requirements.txt
```
NOTE: For GraphViz you need to additionally download its binaries and add it to your `PATH` (Refer [here](https://graphviz.org/download/)).
2. Installing the Bicycle Compiler (optional; if you don't want backend resource estimates, you can comment out the `run_backend_demo()` function call in `end_to_end_demo.py`):
  - Clone the GitHub repository (in some other directory):
    ```bash
    git clone https://github.com/qiskit-community/bicycle-architecture-compiler.git
    cd bicycle-architecture-compiler
    ```
  - Build the Binaries with Internal Gridsynth: Build the Rust workspace in release mode, 
   activating the `rsgridsynth` feature so that all arbitrary angle rotations can be synthesized 
   using native Rust code without external dependencies.
   ```bash
   cargo build --release -F rsgridsynth
   ```
   [from the root of the repo, where Cargo.toml is located]
  - Locate the Compiled Binaries: Once compilation is done, the executables will be located in the `target\release folder`. 
   The primary binaries you need are:
        - `bicycle_compiler.exe`
        - `bicycle_numerics.exe`
    [You can either add it globally to environment `PATH` or copy-paste these binaries in a directory within your workspace]
    Note: For the current implementation, copy-paste the binaries into the `bicycle_compiler_binaries` directory (for example, this repository has the executables compiled for Windows 64-bit saved in the directory; compiled using the Feb 2026 version of the bicycle compiler repository).
  - Generate the Measurement Tables (One-time Setup): The compiler relies on pre-generated measurement tables for optimization. 
   You should generate these to a dedicated folder that your Python script will know about.
    ```bash
    .\bicycle_compiler gross generate table_gross.dat
    .\bicycle_compiler two-gross generate table_two-gross.dat
    ```
    [You should run these after `cd` to the directory of the executables]
    [You should take these generated `.dat` tables and place them into a directory within your workspace]
    [For example, store them in a directory named `measurement_tables`]

### Running the Demo 
Execute the following to run the demo scripts:
```bash
python end_to_end_demo.py
```
After execution, the results will be saved to the following the subdirectories of the `example-outputs` directory:
- Algorithmic level: `example-outputs/algorithmic-level`
- Logical level: `example-outputs/logical-level`
- PBC level: `example-outputs/pbc-level`
- Backend integration: `example-outputs/backend-integration`

Some sample outputs are provided based on running the script already in `example-outputs`. You may try modifying the demo script or implement your own circuits to test the end-to-end resource estimation pipeline.

## Sample Outputs
Note: Different circuits are used for these sample outputs (for demonstration purposes).
### 1. Algorithmic Level:
#### Original `QuantumCircuit`: 

<img width="990" height="551" alt="Image" src="https://github.com/user-attachments/assets/04841db7-0cc8-4e6e-87fc-dfaafe98d8b1" />

#### Corresponding Resource Tree (Using `GraphViz`):

<img width="3191" height="696" alt="Image" src="https://github.com/user-attachments/assets/8a72c0ab-4d02-4f35-9f6b-dfadda9a5370" />

#### Pie Chart of The Total Operation Counts at Tree Depth 1:

<img width="1189" height="590" alt="Image" src="https://github.com/user-attachments/assets/972af5b5-05bc-4b7d-89e5-d31f1012c88e" />

#### Table of Operations at Tree Depth 1:

|Name   |Type             |Qubits|Clbits|Occurrences|Total Ops|Abs Level|barrier|cx |measure|u  |
|-------|-----------------|------|------|-----------|---------|---------|-------|---|-------|---|
|h      |_SingletonHGate  |1     |0     |1          |1        |composite|0      |0  |0      |1  |
|qft    |QFTGate          |3     |0     |1          |21       |composite|0      |9  |0      |12 |
|cx     |_SingletonCXGate |2     |0     |1          |1        |primitive|0      |1  |0      |0  |
|barrier|Barrier          |4     |0     |1          |1        |primitive|1      |0  |0      |0  |
|measure|_SingletonMeasure|1     |1     |4          |1        |primitive|0      |0  |1      |0  |

### 2. Logical Level:
The following outputs were obtained using `gridsynth` with `eps=1e-6` and `basis_gates = get_clifford_gate_names() + ["t", "tdg"]` (the demo also uses other `eps` for `gridsynth` and the `basis_set = get_clifford_gate_names() + ["rz", "t", "tdg"]` as well).
#### Bar Chart of The Class Total Breakdowns:

<img width="790" height="490" alt="Image" src="https://github.com/user-attachments/assets/41b00c34-7772-465d-8d8c-ef8f89de4be6" />

Here, a different circuit without any measurements was used.
#### Bar Chart of The Clifford Gate Type Breakdowns:

<img width="1089" height="490" alt="Image" src="https://github.com/user-attachments/assets/2ef55886-6d6c-4f2a-86d0-9f7647f3a27a" />

#### Pie Chart of the Non-Clifford Gate Type Breakdowns (`T` and `Tdg` in this case):

<img width="1090" height="490" alt="Image" src="https://github.com/user-attachments/assets/d08ca237-9afd-4204-8232-9b16044c6c77" />

#### Comparison Table of The Clifford and Non-Clifford Gate Costs When Using Different `eps` Values for `gridsynth`:

|method   |epsilon|depth|size|clifford|non_clifford|t_like|
|---------|-------|-----|----|--------|------------|------|
|gridsynth|1e-06  |460  |895 |523     |372         |372   |
|gridsynth|1e-07  |556  |1067|633     |434         |434   |
|gridsynth|1e-08  |556  |1099|627     |472         |472   |

Here, the `t_like` count is equal to the `non_clifford` count because the basis is only Clifford + T-like (`t`/`tdg`) gates.

### 3. PBC Level:
#### PBC Primitive Counts:

<img width="1089" height="490" alt="Image" src="https://github.com/user-attachments/assets/3e4caf6b-3d92-4e7d-9f37-a59c4d6cdf80" />

#### JSON Summary of The Compiled PBC Circuit:
```json
{
  "pbc": {
    "name": "backend_evolution_demo",
    "depth": 77,
    "width": 20,
    "size": 370,
    "type": "QuantumCircuit"
  },
  "operation_counts": {
    "PauliEvolution": 360,
    "pauli_product_measurement": 10
  },
  "totals": {
    "total_ops": 370,
    "pauli_evolution": 360,
    "pauli_product_measurement": 10
  }
}
```
These PBC primitive counts were obtained from the compiled `QuantumCircuit` after applying the `LitinskiTransformation` pass.

### 4. Physical Level:
#### QFT Circuit:
The backend integration with the bicycle code compiler was run for a simple QFT (Quantum Fourier Transform) circuit:

<img width="700" height="551" alt="Image" src="https://github.com/user-attachments/assets/8d2fcd99-0762-4b70-a8fc-a70b52b9794b" />

Following this, the outputs from running the compiler were generated.
#### Accumulated Logical Error vs Measurement Depth Graph:

<img width="2618" height="1638" alt="Image" src="https://github.com/user-attachments/assets/9b065369-a0de-4c82-9adb-eeb96c8eec27" />

#### Table of Benchmarking The Circuit:

|code |p     |i  |qubits|idles|t_injs|automorphisms|measurements|joint_measurements|measurement_depth|end_time|total_error       |
|-----|------|---|------|-----|------|-------------|------------|------------------|-----------------|--------|------------------|
|gross|0.0001|1  |11    |0    |95    |2            |3           |0                 |3                |22163   |0.0000835080302428|
|gross|0.0001|2  |11    |0    |91    |8            |7           |0                 |10               |43986   |0.0001635041009712|
|gross|0.0001|3  |11    |0    |91    |8            |7           |0                 |17               |65809   |0.0002435001716996|
|gross|0.0001|4  |11    |0    |94    |8            |7           |0                 |24               |88319   |0.000326133242428 |
|gross|0.0001|5  |11    |0    |94    |28           |20          |0                 |44               |112581  |0.0004087794441276|
|gross|0.0001|6  |11    |0    |91    |28           |20          |0                 |64               |136156  |0.0004887886458272|
|gross|0.0001|7  |11    |0    |91    |28           |20          |0                 |84               |159731  |0.0005687978475268|
|gross|0.0001|8  |11    |0    |92    |2            |2           |0                 |86               |181087  |0.0006496678677696|
|gross|0.0001|9  |11    |0    |91    |8            |7           |0                 |93               |202910  |0.000729663938498 |
|gross|0.0001|10 |11    |0    |91    |8            |7           |0                 |100              |224733  |0.0008096600092264|
|gross|0.0001|11 |11    |0    |91    |28           |20          |0                 |120              |248308  |0.000889669210926 |
|gross|0.0001|12 |11    |0    |91    |28           |20          |0                 |140              |271883  |0.0009696784126256|
|gross|0.0001|13 |11    |0    |91    |2            |2           |0                 |142              |293010  |0.0010496694328684|
|gross|0.0001|14 |11    |0    |91    |8            |7           |0                 |149              |314833  |0.0011296655035968|
|gross|0.0001|15 |11    |0    |91    |28           |20          |0                 |169              |338408  |0.0012096747052964|
|gross|0.0001|16 |11    |0    |0     |12           |8           |0                 |177              |339512  |0.0012096827860248|
|gross|0.0001|17 |11    |0    |0     |12           |8           |0                 |185              |340616  |0.0012096908667532|
|gross|0.0001|18 |11    |0    |0     |12           |8           |0                 |193              |341720  |0.0012096989474816|
|gross|0.0001|19 |11    |0    |0     |2            |2           |0                 |195              |342008  |0.0012097009677244|

You can refer to [`end_to_end_demo.py`](end_to_end_demo.py) for more examples and testing with a more complex Pauli evolution circuit. 

## License
[MIT License](LICENSE)
