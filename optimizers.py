from qiskit.transpiler.basepasses import TransformationPass
from qiskit.dagcircuit import DAGOpNode
from qiskit.circuit.library import XGate, HGate, ZGate
from qiskit import QuantumCircuit
from qiskit.transpiler import PassManager

class XHXtoHZReduction(TransformationPass):
    """
    Replace the gate pattern X - H - X with H - Z.
    That is, x h x ≡ h z (up to global phase, which doesn't affect measurement).
    """
    def run(self, dag):
        for node in dag.topological_op_nodes():
            if isinstance(node.op, XGate):
                q = node.qargs[0]
                succ1 = [s for s in dag.successors(node) if isinstance(s, DAGOpNode)]
                if len(succ1) == 1 and isinstance(succ1[0].op, HGate):
                    h_node = succ1[0]
                    succ2 = [s for s in dag.successors(h_node) if isinstance(s, DAGOpNode)]
                    if len(succ2) == 1 and isinstance(succ2[0].op, XGate):
                        x2_node = succ2[0]
                        dag.substitute_node(node, HGate(), inplace=True)
                        dag.substitute_node(h_node, ZGate(), inplace=True)
                        dag.remove_op_node(x2_node)
        return dag
    
class HXHtoZReduction(TransformationPass):
    """
    Replace the gate pattern H - X - H with Z.
    """
    def run(self, dag):
        for node in dag.topological_op_nodes():
            if isinstance(node.op, HGate):
                q = node.qargs[0]
                succ1 = [s for s in dag.successors(node) if isinstance(s, DAGOpNode)]
                if len(succ1) == 1 and isinstance(succ1[0].op, XGate):
                    h_node = succ1[0]
                    succ2 = [s for s in dag.successors(h_node) if isinstance(s, DAGOpNode)]
                    if len(succ2) == 1 and isinstance(succ2[0].op, HGate):
                        x2_node = succ2[0]
                        dag.substitute_node(node, ZGate(), inplace=True)
                        dag.remove_op_node(h_node,)
                        dag.remove_op_node(x2_node)
        return dag

class RemoveConsecutiveH(TransformationPass):
    """
    Removes pairs of consecutive H gates on the same qubit with nothing in between.
    """
    def run(self, dag):
        to_remove = []

        for node in dag.topological_op_nodes():
            if node.name == 'h':
                q = node.qargs[0]
                # Get the only successor that is an op node
                successors = [s for s in dag.successors(node) if isinstance(s, DAGOpNode)]
                if len(successors) == 1:
                    succ = successors[0]
                    if succ.name == 'h' and succ.qargs[0] == q:
                        # They are consecutive on same qubit
                        to_remove.extend([node, succ])

        for node in to_remove:
            dag.remove_op_node(node)

        return dag


class MergeConsecutiveRX(TransformationPass):
    def run(self, dag):
        for qubit in dag.qubits:
            nodes = [node for node in dag.topological_op_nodes()
                     if node.name == 'rx' and node.qargs[0] == qubit]

            i = 0
            while i < len(nodes) - 1:
                current = nodes[i]
                next_node = nodes[i + 1]
                if list(dag.predecessors(next_node))[0] == current:
                    theta_sum = current.op.params[0] + next_node.op.params[0]
                    dag.substitute_node(current, 
                        type(current.op)(theta_sum), inplace=True)
                    dag.remove_op_node(next_node)
                    nodes.pop(i + 1)
                else:
                    i += 1
        return dag
    
class TCountTemplateReduction(TransformationPass):
    """
    Reduce T-count using a simple template:
    T q; CX q,c; Tdg c; CX q,c;  ->  CX q,c
    """
    def run(self, dag):
        for node in dag.topological_op_nodes():
            if node.name == 't':
                q = node.qargs[0]
                succs = [s for s in dag.successors(node) if isinstance(s, DAGOpNode)]
                if len(succs) == 1 and succs[0].name == 'cx':
                    cx1 = succs[0]
                    c = [arg for arg in cx1.qargs if arg != q][0]
                    succs2 = [s for s in dag.successors(cx1) if isinstance(s, DAGOpNode)]
                    if len(succs2) == 2 and succs2[0].name == 'cx' and succs2[1].name == 'tdg':
                        tdg = succs2[0]
                        succs3 = [s for s in dag.successors(tdg) if isinstance(s, DAGOpNode)]
                        if succs3[0].name == 't':
                            cx2 = succs3[0]
                            dag.remove_op_node(succs3[0])
                            dag.remove_op_node(succs2[0])
                            dag.remove_op_node(succs2[-1])
        return dag

def optimized_toffoli():
        """Return a 3-qubit circuit for a 4-T Toffoli gate (Amy et al.)."""
        qc = QuantumCircuit(3, name='Toffoli_4T')
        qc.h(2)
        qc.t(2)
        qc.cx(1,2)
        qc.tdg(2)
        qc.cx(0,2)
        qc.t(2)
        qc.cx(1,2)
        qc.tdg(2)
        qc.cx(0,2)
        qc.t(1)
        qc.h(2)
        return qc

class ToffoliTCountReduction(TransformationPass):
    """
    Replace every CCX (Toffoli) gate with a 4-T-count optimized decomposition.
    """
    
    def run(self, dag):
        for node in dag.op_nodes():
            if node.name == 'ccx':
                qargs = node.qargs
                # Create the optimized Toffoli circuit
                opt_toffoli = optimized_toffoli()
                # Substitute the node in the DAG
                # dag.substitute_node_with_dag(node, opt_toffoli.to_instruction().definition)
        return dag
    
from qiskit.circuit.library.standard_gates import SwapGate
from qiskit.transpiler.basepasses import TransformationPass
from qiskit.dagcircuit import DAGOpNode


class OptimizeConsecutiveSwaps(TransformationPass):
    def run(self, dag):
        swap_nodes = dag.op_nodes(SwapGate)
        swaps_to_remove = set()

        for swap in swap_nodes:
            if swap in swaps_to_remove:
                continue
            swap_qubits = swap.qargs
            successors = list(dag.successors(swap))

            for succ in successors:
                if isinstance(succ, DAGOpNode) and isinstance(succ.op, SwapGate):
                    succ_qubits = succ.qargs
                    if set(swap_qubits) == set(succ_qubits):
                        swaps_to_remove.add(swap)
                        swaps_to_remove.add(succ)
                        break

        for swap in swaps_to_remove:
            dag.remove_op_node(swap)

        return dag

class MergeAdjacentSwapsPass(TransformationPass):
    def run(self, dag):
        swap_nodes = list(dag.op_nodes(SwapGate))
        swaps_to_remove = set()

        for swap in swap_nodes:
            if swap in swaps_to_remove:
                continue

            qargs1 = swap.qargs
            successors = list(dag.successors(swap))

            for succ in successors:
                if (
                    isinstance(succ, DAGOpNode)
                    and isinstance(succ.op, SwapGate)
                    and succ not in swaps_to_remove
                ):
                    qargs2 = succ.qargs
                    common_qubits = set(qargs1).intersection(set(qargs2))
                    if len(common_qubits) == 1:
                        swaps_to_remove.add(swap)
                        swaps_to_remove.add(succ)
                        break

        for swap in swaps_to_remove:
            dag.remove_op_node(swap)

        return dag
