# QREX (Quantum Resource EXplorer)
## An End-to-End Resource Estimation Tool for Fault-Tolerant Quantum Algorithms in Qiskit
<p align="center">
  <img width="500" alt="QREX-Logo" src="https://github.com/user-attachments/assets/b19f4b01-68af-421d-ad30-f592302b93dd" />
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
  - Refers to the Pauli-based Computation level primitives (namely product pauli rotations (implemented a `PauliEvolutionGate` operations) and product pauli measurements (implemented as `PauliProductMeasurement` operations)).
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

## License
[MIT License](LICENSE)
