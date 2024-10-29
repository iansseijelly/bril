# Basic Block Dead Code Elimination
import json
import sys
import networkx as nx
from collections import OrderedDict

CF_OPs = ["br", "jmp"]

class BasicBlock:
    def __init__(self, label: str = None):
        self.instrs : list[dict] = []
        self.label : str = label
    
    def __str__(self):
        return f"BasicBlock(label={self.label}, instrs={self.instrs})"

    def __lt__(self, other):
        return self.label < other.label

    def add_instr(self, instr: dict):
        self.instrs.append(instr)    

def construct_cfg(instrs):
    cfg = nx.DiGraph()
    entry_block = BasicBlock("sentinel_entry")
    curr_block = entry_block
    cfg.add_node(entry_block)
    blocks = OrderedDict({"sentinel_entry": entry_block}) # dummy label marking the entry node
    # the node pass
    for instr in instrs:
        if "label" in instr and instr["label"] != "sentinel_entry":
            curr_block = BasicBlock(instr["label"])
            cfg.add_node(curr_block)
            blocks[instr["label"]] = curr_block
        curr_block.add_instr(instr)
    for node in cfg.nodes:
        log_file.write(f"{node.label}\n")
    # the edge pass
    for (i,u) in enumerate(cfg.nodes):
        if u.instrs and "op" in u.instrs[-1] and u.instrs[-1]["op"] in CF_OPs:
            for label in u.instrs[-1]["labels"]:
                cfg.add_edge(u, blocks[label])
                log_file.write(f"{u.label} -> {blocks[label].label}\n")
        # normal fallthrough
        else:
            if i+1 < len(blocks):
                next_block = blocks[list(blocks.keys())[i+1]]
                cfg.add_edge(u, next_block)
                log_file.write(f"{u.label} -> {next_block.label}\n")
    return cfg, entry_block

# insert a node target_node before before_node
def insert_node_before(cfg, target_node, before_node):
    node_list = list(cfg.nodes)
    edge_list = list(cfg.edges)
    for i, node in enumerate(node_list):
        if node == before_node:
            node_list.insert(i, target_node)
            break
    cfg.clear()
    cfg.add_nodes_from(node_list)
    cfg.add_edges_from(edge_list)

# insert a node target_node after after_node
def insert_node_after(cfg, target_node, after_node):
    node_list = list(cfg.nodes)
    edge_list = list(cfg.edges)
    for i, node in enumerate(node_list):
        if node == after_node:
            node_list.insert(i+1, target_node)
            break
    cfg.clear()
    cfg.add_nodes_from(node_list)
    cfg.add_edges_from(edge_list)

def cfg_to_instrs(cfg):
    program = []
    # get the very first instruction
    first_instr = next(iter(cfg.nodes))
    if first_instr.instrs and first_instr.instrs[0].get("label", None) != "sentinel_entry":
        program.append({"label": "sentinel_entry"})
    for block in cfg.nodes:
        program.extend(block.instrs)
    return program


TERMINATORS = ["br", "jmp", "ret"]

def add_terminators(cfg: nx.DiGraph):
    """Given a CFG, modify the blocks to add terminators
    to all blocks (avoiding "fall-through" control flow transfers).
    """
    blocks = list(cfg.nodes)
    for i, block in enumerate(blocks):
        if not block.instrs or len(block.instrs) <= 1:
            if i == len(blocks) - 1:
                # In the last block, return.
                block.add_instr({'op': 'ret', 'args': []})
            else:
                dest = blocks[i + 1].label
                block.add_instr({'op': 'jmp', 'labels': [dest]})
        elif block.instrs[-1]['op'] not in TERMINATORS:
            if i == len(blocks) - 1:
                block.add_instr({'op': 'ret', 'args': []})
            else:
                # Otherwise, jump to the next block.
                dest = blocks[i + 1].label
                block.add_instr({'op': 'jmp', 'labels': [dest]})
        
        # Update CFG edges
        if block.instrs[-1]['op'] == 'jmp':
            cfg.add_edge(block, blocks[i + 1])

log_file = open('log/cfg.log', 'w')