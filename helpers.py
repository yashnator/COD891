from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag
import matplotlib.pyplot as plt
from qiskit.dagcircuit.dagnode import DAGOpNode, DAGInNode, DAGOutNode
from qiskit import QuantumCircuit
from qiskit.circuit.library import GroverOperator, MCMT, ZGate
from qiskit.visualization import plot_distribution

def print_dag_nodes(dag):
    for node in dag.topological_nodes():
        if isinstance(node, DAGOpNode):
            print("DAGOpNode:")
            print(f"  Name: {node.name}")
            print(f"  Op: {node.op}")
            print(f"  Qubits: {node.qargs}")
            print(f"  Cbits: {node.cargs}")
        elif isinstance(node, DAGInNode):
            print("DAGInNode:")
            print(f"  Wire: {node.wire}")
        elif isinstance(node, DAGOutNode):
            print("DAGOutNode:")
            print(f"  Wire: {node.wire}")
        else:
            print(f"Unknown node type: {type(node)}")
        print("---")

def grover_oracle(marked_states):
    """Build a Grover oracle for multiple marked states

    Here we assume all input marked states have the same number of bits

    Parameters:
        marked_states (str or list): Marked states of oracle

    Returns:
        QuantumCircuit: Quantum circuit representing Grover oracle
    """
    if not isinstance(marked_states, list):
        marked_states = [marked_states]
    # Compute the number of qubits in circuit
    num_qubits = len(marked_states[0])

    qc = QuantumCircuit(num_qubits)
    # Mark each target state in the input list
    for target in marked_states:
        # Flip target bit-string to match Qiskit bit-ordering
        rev_target = target[::-1]
        # Find the indices of all the '0' elements in bit-string
        zero_inds = [ind for ind in range(num_qubits) if rev_target.startswith("0", ind)]
        # Add a multi-controlled Z-gate with pre- and post-applied X-gates (open-controls)
        # where the target bit-string has a '0' entry
        qc.x(zero_inds)
        qc.compose(MCMT(ZGate(), num_qubits - 1, 1), inplace=True)
        qc.x(zero_inds)
    return qc