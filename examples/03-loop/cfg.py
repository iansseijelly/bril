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
        if "label" in instr:
            curr_block = BasicBlock(instr["label"])
            cfg.add_node(curr_block)
            blocks[instr["label"]] = curr_block
        curr_block.add_instr(instr)
    # the edge pass
    for (i,u) in enumerate(cfg.nodes):
        if u.instrs and "op" in u.instrs[-1] and u.instrs[-1]["op"] in CF_OPs:
            for label in u.instrs[-1]["labels"]:
                cfg.add_edge(u, blocks[label])
        # normal fallthrough
        else:
            if i+1 < len(blocks):
                next_block = blocks[list(blocks.keys())[i+1]]
                cfg.add_edge(u, next_block)

    return cfg, entry_block
    return cfg, entry_block

def cfg_to_instrs(cfg):
    program = []
    for block in cfg.nodes:
        program.extend(block.instrs)
    return program