# Run SSA before running this
# Loop invariant code motion

import json
import sys
import cfg
import ssa
import networkx as nx

invar_ops = ["add", "sub", "mul", "div", "mod", "eq", "lt", "gt", "le", "ge"]

class Loop:
    def __init__(self, backedge: tuple[cfg.BasicBlock, cfg.BasicBlock], loop_body: set[cfg.BasicBlock]):
        self.header = backedge[1]
        self.latch = backedge[0]
        self.body = loop_body

    def __str__(self):
        return f"Loop(header={self.header.label}, latch={self.latch.label}, body={[b.label for b in self.body]})"
    
# A->B, A dominated by B, then (A, B) is a backedge
def find_backedges(cfg: nx.DiGraph, dom: dict[cfg.BasicBlock, set[cfg.BasicBlock]]):
    back_edges = []
    log_file.write("--- CFG ---\n")
    for edge in cfg.edges:
        log_file.write(f"{edge[0].label} -> {edge[1].label}\n")
    for u in cfg.nodes:
        log_file.write(f"--- {u.label} ---\n")
        for v in cfg.successors(u):
            log_file.write(f"{v.label} is a successor of {u.label}\n")
            if v in dom[u]:
                back_edges.append((u, v))
    log_file.write("Back edges:\n")
    for u, v in back_edges:
        log_file.write(f"{u.label} -> {v.label}\n")
    return back_edges

def find_natural_loops(cfg: nx.DiGraph, back_edge: tuple[cfg.BasicBlock, cfg.BasicBlock]):
    u, v = back_edge
    # Find all nodes in the back edge
    nodes = set()
    nodes.add(u)
    nodes.add(v)

    stack = [u]
    while stack:
        node = stack.pop()
        for pred in cfg.predecessors(node):
            if pred not in nodes and pred != v:
                nodes.add(pred)
                stack.append(pred)
    log_file.write(f"Loop for backedge {u.label} -> {v.label}:\n")
    loop = Loop(back_edge, nodes)
    log_file.write(f"{loop}\n")
    return loop

def find_all_natural_loops(cfg: nx.DiGraph, back_edges: list[tuple[cfg.BasicBlock, cfg.BasicBlock]]):
    loops = []
    for back_edge in back_edges:
        nodes = find_natural_loops(cfg, back_edge)
        loops.append(nodes)
    return loops

# for a loop, specify all loop invariant defs 
def build_loop_def_map(loop: Loop):
    invariant_map = set()
    for block in loop.body:
        for instr in block.instrs:
            if "dest" in instr:
                invariant_map.add(instr["dest"])
    return invariant_map

def build_non_loop_invar_map(cfg: nx.DiGraph, loop: Loop, func):
    """
    Treat loop as a black box, what is invariant outside the loop?
    """
    invariant_map = set(ssa.get_arg_names(func))
    worklist = list(cfg.nodes)
    while worklist:
        node = worklist.pop()
        if node not in loop.body:
            for instr in node.instrs:
                if "dest" in instr:
                    invariant_map.add(instr["dest"])
    log_file.write(f"Non-loop invariant map: {invariant_map}\n")
    return invariant_map

def build_loop_invar_map(cfg: nx.DiGraph, loop: Loop, func):
    log_file.write(f"Building invariant map for loop {loop.header.label}\n")
    insertion_map = [] # list of tuple (block, instr)
    # build invariant map for defs outside the loop
    invariant_map = build_non_loop_invar_map(cfg, loop, func)
    # recursively find invariant assignments
    if invariant_map:
        while True:
            changed = False
            for node in loop.body:
                for instr in node.instrs:
                    # if all args are invariant
                    if "args" in instr and all(arg in invariant_map for arg in instr["args"]) \
                        and "op" in instr and instr["op"] in invar_ops and instr["dest"] not in invariant_map:
                        invariant_map.add(instr["dest"])
                        # if the predecessor of loop header is singular, excluding the backedge
                        log_file.write(f"candidate: {instr}\n")
                        predecessors = list(cfg.predecessors(loop.header))
                        non_backedge_preds = [p for p in predecessors if p != loop.latch]
                        if len(non_backedge_preds) == 1:
                            log_file.write(f"singular predecessor: {non_backedge_preds[0].label}\n")
                            loop.pre_header = non_backedge_preds[0]
                            # move the instruction up
                            insertion_map.append((loop.pre_header, instr.copy()))
                            log_file.write(f"appenede {instr} to {loop.pre_header.label}\n")
                            instr["op"] = "nop"
                        else:
                            log_file.write(f"non-singular predecessor: {predecessors}\n")
                        changed = True
            if not changed:
                break
    log_file.write(f"Invariant map: {invariant_map}\n")
    return invariant_map, insertion_map

# find all loop-invariant assignments
def find_loop_invar(loop: Loop, cfg: nx.DiGraph, func):
    candidates = []
    invariant_map, insertion_map = build_loop_invar_map(cfg, loop, func)
    log_file.write(f"Insertion map: {[(block.label, instr) for block, instr in insertion_map]}\n")
    return invariant_map, insertion_map

def insert_instructions(program_cfg, insertion_map):
    for block in program_cfg.nodes:
        for target_block, instr in insertion_map:
            if block == target_block:
                log_file.write(f"Inserting {instr} into {block.label}\n")
                new_instrs = block.instrs[:-1]
                new_instrs.append(instr)
                new_instrs.append(block.instrs[-1])
                block.instrs = new_instrs
                log_file.write(f"New instructions: {block.instrs}\n")

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    log_file = open("log/licm.log", "w")
    for fn in prog["functions"]:
        program_cfg, entry_block = cfg.construct_cfg(fn["instrs"])
        dom = ssa.get_dominators(program_cfg, entry_block)
        back_edges = find_backedges(program_cfg, dom)
        loops = find_all_natural_loops(program_cfg, back_edges)
        for loop in loops:
            invariant_map, insertion_map = find_loop_invar(loop, program_cfg, fn)
            insert_instructions(program_cfg, insertion_map)
        fn["instrs"] = cfg.cfg_to_instrs(program_cfg)
    json.dump(prog, sys.stdout, indent=2)
    log_file.close()
