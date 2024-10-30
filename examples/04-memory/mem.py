import json
import sys
import cfg
import networkx as nx
from collections import OrderedDict

def get_arg_names(func):
    return {arg["name"] for arg in func.get("args", [])}

def union_pointer_sets(pointer_sets):
    """
    pointer_sets is a list of strings
    """
    # remove all None values
    pointer_sets = [ps for ps in pointer_sets if ps is not None]
    return set().union(*pointer_sets)

def intersect_pointer_maps(pred_pointer_maps):
    # gather all possible keys
    ret_map = {}
    keys = set()
    for pred_pointer_map in pred_pointer_maps:
        keys.update(pred_pointer_map.keys())
    for k in keys:
        values = [pred_pointer_map.get(k, None) for pred_pointer_map in pred_pointer_maps]
        ret_map[k] = union_pointer_sets(values)
    return ret_map

def mark_use(use_map, argument, block_pointer_map):
    log_file.write(f"Marking use for {argument} in {block_pointer_map}\n")
    pointer = block_pointer_map.get(argument, None)
    if pointer is None:
        return
    if "any" in pointer:
        # mark all use as True
        for use in use_map.values():
            use = (use[0], True)
        # check for aliasing
    for store_dest in use_map.keys():
        if pointer.intersection(block_pointer_map.get(store_dest, set())):
            use_map[store_dest] = (use_map[store_dest][0], True) # hack to modify tuple


def mem_analysis(cfg, entry_block, arg_names):
    pointer_map : dict[str, dict[str, set[str]]] = {} # a per-block pointer map
    # init all pointer maps to empty
    for block in cfg.nodes:
        pointer_map[block.label] = {}
    # initialize the pointer map for function entry
    pointer_map[entry_block.label] = {arg: {"any"} for arg in arg_names}
    post_order = list(list(nx.dfs_postorder_nodes(cfg, source=entry_block)))
    worklist = post_order
    while worklist:
        block = worklist.pop()
        log_file.write(f"Processing block {block.label}\n")
        predecessors = list(cfg.predecessors(block))
        block_pointer_map = intersect_pointer_maps([pointer_map[pred.label] for pred in predecessors])
        store_use_map = {}
        for i, instr in enumerate(block.instrs):
            if "op" in instr:
                match instr["op"]:
                    case "alloc":
                        block_pointer_map[instr["dest"]] = {f"{block.label}.{i}"}
                    case "load":
                        block_pointer_map[instr["dest"]] = {"any"} # since we do not model memory, it can point anywhere
                        mark_use(store_use_map, instr["args"][0], block_pointer_map)
                    case "id" | "ptradd":
                        if instr["args"][0] in block_pointer_map:
                            block_pointer_map[instr["dest"]] = block_pointer_map[instr["args"][0]]
                    case "store":
                        store_dest_ptr = instr["args"][0]
                        prev_store_insn, used = store_use_map.get(store_dest_ptr, (None, True))
                        log_file.write(f"Prev store for {store_dest_ptr}: {prev_store_insn}\n")
                        if not used:
                            prev_store_insn["op"] = "nop"
                            log_file.write(f"Marking {instr['args'][0]} as unused NOP!\n")
                        store_use_map[store_dest_ptr] = (instr, False)
                        log_file.write(f"Marking most recent store for {store_dest_ptr} as {instr}\n")
                    case _:
                        pass
        if block.label not in pointer_map or pointer_map[block.label] != block_pointer_map:
            log_file.write(f"Updating pointer map for block {block.label}\n")
            for k, v in block_pointer_map.items():
                log_file.write(f"  {k}: {v}\n")
            pointer_map[block.label] = block_pointer_map
            worklist.extend(cfg.successors(block))

if __name__ == "__main__":
    log_file = open("log/mem.log", "w")
    prog = json.load(sys.stdin)
    log_file.write(f"Processing {len(prog['functions'])} function(s)\n")
    for fn in prog["functions"]:
        log_file.write(f"--> Processing function {fn['name']} -->\n")
        program_cfg, entry_block = cfg.construct_cfg(fn["instrs"])
        arg_names = get_arg_names(fn)
        mem_analysis(program_cfg, entry_block, arg_names)
    json.dump(prog, sys.stdout, indent=2)
