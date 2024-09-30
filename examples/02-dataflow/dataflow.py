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

def union_live_sets(succ_live_sets: list[set]):
    """
    Given a list of live sets, return the union of all the live sets.

    Args:
        succ_live_sets: a list of live sets

    Returns:
        the union of all the live sets
    """
    return set().union(*succ_live_sets)

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
    const_map : dict[str, dict] = {} # a per-block const map
    # reverse the post order of the cfg
    post_order = list(list(nx.dfs_postorder_nodes(cfg, source=entry_block)))
    worklist = post_order

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

def should_keep(instr):
    if "op" not in instr:
        return True
    return instr["op"] != "nop"

def remove_nops(instrs):
    return [instr for instr in instrs if should_keep(instr)]

def used_locally(block, target_insn):
    """
    Check if the destination of this instruction is used locally LATER.

    Args:
        block: the block containing the instruction
        insn: the instruction

    Returns:
        True if the destination is used locally, False otherwise
    """
    found = False
    for i, curr_insn in enumerate(block.instrs):
        if curr_insn == target_insn:
            found = True
        if found and "args" in curr_insn and target_insn["dest"] in curr_insn["args"]:
            return True
    return False

def live_variable_analysis(cfg, entry_block):
    in_map : dict[str, set] = {} # a per-block live map (in)
    out_map : dict[str, set] = {} # a per-block live map (out)
    post_order = list(reversed(list(nx.dfs_postorder_nodes(cfg, source=entry_block))))
    worklist = post_order

    while worklist:
        block = worklist.pop()
        log_file.write(f"Processing block {block.label}\n")
        successors = list(cfg.successors(block))
        log_file.write(f"Successors labels: {[succ.label for succ in successors]}\n")
        block_out_map = union_live_sets([in_map.get(succ.label, set()) for succ in successors])
        log_file.write(f"block_out_map: {block_out_map}\n")
        if block.label not in out_map or out_map[block.label] != block_out_map:
            out_map[block.label] = block_out_map
            log_file.write(f"Updating out_map for block {block.label}\n")
        log_file.write(f"out_map: {out_map}\n")
        block_in_map = block_out_map.copy()
        for i, insn in reversed(list(enumerate(block.instrs))):
            if "dest" in insn:
                if insn["dest"] in block_in_map:
                    block_in_map.remove(insn["dest"])
            for arg in insn.get("args", []):
                block_in_map.add(arg)
        if block.label not in in_map or in_map[block.label] != block_in_map:
            in_map[block.label] = block_in_map
            log_file.write(f"Updating in_map for block {block.label}\n")
            log_file.write(f"in_map: {in_map}\n")
            worklist.extend(cfg.predecessors(block))
    
    for block in cfg.nodes:
        for i, insn in reversed(list(enumerate(block.instrs))):
            if "dest" in insn and insn["dest"] not in out_map[block.label] and not used_locally(block, insn):
                log_file.write(f"Marking {insn} as dead for block {block.label}\n")
                block.instrs[i]["op"] = "nop"
    
    for block in cfg.nodes:
        block.instrs = remove_nops(block.instrs)

if __name__ == "__main__":
    log_file = open("log/dataflow.log", "w")
    prog = json.load(sys.stdin)
    log_file.write(f"Processing {len(prog['functions'])} function(s)\n")
    for fn in prog["functions"]:
        log_file.write(f"--> Processing function {fn['name']} -->\n")
        program_cfg, entry_block = cfg.construct_cfg(fn["instrs"])
        const_prop_and_fold(program_cfg, entry_block)
        live_variable_analysis(program_cfg, entry_block)
        fn["instrs"] = cfg.cfg_to_instrs(program_cfg)
    json.dump(prog, sys.stdout, indent=2)