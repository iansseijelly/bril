import json
import sys
import cfg
import networkx as nx
from collections import OrderedDict

def all_same(values: list):
    """
    Check if all the values in the list are the same.

    Args:
        values: a list of values

    Returns:
        True if all the values are the same, False otherwise
    """
    return len(set(values)) == 1

def intersect_const_maps(pred_const_maps: list[dict]):
    """
    Given a list of const maps, return the intersection of all the const maps.

    Args:
        const_maps: a list of const maps

    Returns:
        inter_const_map: the intersection of all the const maps
    """
    all_keys = set().union(*pred_const_maps)
    inter_const_map = {}
    for key in all_keys:
        values = [pred_const_map.get(key, None) for pred_const_map in pred_const_maps]
        # if all the values are the same, then we can set the value to that
        if all_same(values):
            inter_const_map[key] = values[0]
    log_file.write(f"Intersected const map: {inter_const_map}\n")
    return inter_const_map

def foldable(insn: dict, block_const_map: dict):
    """
    Check if the instruction is foldable.

    Args:
        insn: an instruction

    Returns:
        True if the instruction is foldable, False otherwise
    """
    foldable_ops = ["add", "sub", "mul"]
    return insn["op"] in foldable_ops and insn["args"][0] in block_const_map and insn["args"][1] in block_const_map

def calc_folded_value(insn: dict, block_const_map: dict):
    """
    Calculate the folded value of the instruction.

    Args:
        insn: an instruction
        block_const_map: a const map of the block

    Returns:
        the folded value of the instruction
    """
    if insn["op"] == "add":
        return block_const_map[insn["args"][0]] + block_const_map[insn["args"][1]]
    elif insn["op"] == "sub":
        return block_const_map[insn["args"][0]] - block_const_map[insn["args"][1]]
    elif insn["op"] == "mul":
        return block_const_map[insn["args"][0]] * block_const_map[insn["args"][1]]
    else:
        return None

def const_prop_and_fold(cfg, entry_block):
    const_map : dict[str, dict] = {}
    # reverse the post order of the cfg
    post_order_rev = list(reversed(list(nx.dfs_postorder_nodes(cfg, source=entry_block))))
    worklist = post_order_rev

    while worklist:
        block = worklist.pop()
        log_file.write(f"Processing block {block.label}\n")
        predecessors = list(cfg.predecessors(block))
        # get the intersection of all predecessors' const maps
        inter_const_map = intersect_const_maps([const_map.get(pred.label, {}) for pred in predecessors])
        block_const_map = inter_const_map
        for i, insn in enumerate(block.instrs):
            if "op" in insn:
                if insn["op"] == "const":
                    block_const_map[insn["dest"]] = insn["value"]
                elif foldable(insn, block_const_map):
                    log_file.write(f"folding {insn['op']} for {insn}\n")
                    block.instrs[i] = {
                        "op": "const",
                        "dest": insn["dest"],
                        "value": calc_folded_value(insn, block_const_map),
                        "type": insn["type"]
                    }
        if block.label not in const_map or const_map[block.label] != block_const_map:
            const_map[block.label] = block_const_map
            worklist.extend(cfg.successors(block))

if __name__ == "__main__":
    log_file = open("log/df_const_prop.log", "w")
    prog = json.load(sys.stdin)
    log_file.write(f"Processing {len(prog['functions'])} function(s)\n")
    for fn in prog["functions"]:
        log_file.write(f"--> Processing function {fn['name']} -->\n")
        program_cfg, entry_block = cfg.construct_cfg(fn["instrs"])
        print(program_cfg)
        const_prop_and_fold(program_cfg, entry_block)
        fn["instrs"] = cfg.cfg_to_instrs(program_cfg)
    json.dump(prog, sys.stdout, indent=2)