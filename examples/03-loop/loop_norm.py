# Run SSA before running this
# Loop invariant code motion

import json
import sys
import cfg
from cfg import BasicBlock, insert_node_before, insert_node_after
import ssa
import networkx as nx

class Loop:
    def __init__(self, backedge: tuple[BasicBlock, BasicBlock], loop_body: set[BasicBlock]):
        self.header = backedge[1]
        self.latch = backedge[0]
        self.body = loop_body

    def __str__(self):
        return f"Loop(header={self.header.label}, latch={self.latch.label}, body={[b.label for b in self.body]})"
    
# A->B, A dominated by B, then (A, B) is a backedge
def find_backedges(cfg: nx.DiGraph, dom: dict[BasicBlock, set[BasicBlock]]):
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

def find_natural_loops(cfg: nx.DiGraph, back_edge: tuple[BasicBlock, BasicBlock]):
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

def change_terminator(block: BasicBlock, old_label: str, new_label: str):
    terminator = block.instrs[-1]
    if "labels" in terminator and old_label in terminator["labels"]:
        terminator["labels"][terminator["labels"].index(old_label)] = new_label

def loop_norm(loops: list[Loop], cfg: nx.DiGraph):
    # build a map of header to loop
    header_to_loop = {}
    for loop in loops:
        if loop.header not in header_to_loop:
            header_to_loop[loop.header] = []
        header_to_loop[loop.header].append(loop)
    for header in header_to_loop:
        loops = header_to_loop[header]
        # create preheader and latch
        pre_header = BasicBlock(f"{header.label}.preheader")
        latch = BasicBlock(f"{header.label}.latch")
        pre_header.instrs = [{"label": f"{header.label}.preheader"}]
        pre_header.instrs.append({"op": "jmp", "labels": [header.label]})
        latch.instrs = [{"label": f"{header.label}.latch"}]
        latch.instrs.append({"op": "jmp", "labels": [header.label]})
        for loop in loops:
            # all non-backedge jumps to header now jump to preheader
            for block in cfg.nodes:
                if block.label != loop.latch.label:
                    change_terminator(block, loop.header.label, f"{pre_header.label}")
            # move all backedges to latch (no longer backedge)
            change_terminator(loop.latch, loop.header.label, f"{latch.label}")
        # insert preheader and latch
        insert_node_before(cfg, pre_header, header)
        insert_node_after(cfg, latch, loops[-1].latch)
        cfg.add_edge(latch, header)

def find_all_natural_loops(cfg: nx.DiGraph, back_edges: list[tuple[BasicBlock, BasicBlock]]):
    loops = []
    for back_edge in back_edges:
        nodes = find_natural_loops(cfg, back_edge)
        loops.append(nodes)
    return loops

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    log_file = open("log/loop_norm.log", "w")
    for fn in prog["functions"]:
        program_cfg, entry_block = cfg.construct_cfg(fn["instrs"])
        cfg.add_terminators(program_cfg)
        dom = ssa.get_dominators(program_cfg, entry_block)
        back_edges = find_backedges(program_cfg, dom)
        loops = find_all_natural_loops(program_cfg, back_edges)
        loop_norm(loops, program_cfg)
        fn["instrs"] = cfg.cfg_to_instrs(program_cfg)
    json.dump(prog, sys.stdout, indent=2)
    log_file.close()
