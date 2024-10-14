import json
import sys
import cfg
import networkx as nx
from collections import defaultdict

def get_def_blocks(cfg: nx.DiGraph):
    """
    Get a map from variable names to defining blocks.
    """
    log_file.write("--- Getting def blocks ---")
    out = defaultdict(set)
    for block in cfg.nodes:
        for instr in block.instrs:
            if 'dest' in instr:
                out[instr['dest']].add(block)
    for var in out:
        log_file.write(f"{var}: {[b.label for b in out[var]]}\n")
    return out

def intersect(sets):
    """
    Intersect a list of sets.
    """
    sets = list(sets)
    if len(sets) == 0:
        return set()
    return set.intersection(*sets)

def get_dominators(cfg: nx.DiGraph, entry: cfg.BasicBlock):
    """
    Get all dominators of a given CFG.
    """
    # log_file.write("--- Getting dominators ---")
    post_order = list(reversed(list(nx.dfs_postorder_nodes(cfg, source=entry))))
    all_nodes = set(cfg.nodes)
    dom = {v: all_nodes for v in cfg.nodes}
    # log_file.write(f"Initial dom:")
    # for block in dom:
        # log_file.write(f"{block.label}: {[b.label for b in dom[block]]}\n")
    while True:
        changed = False
        for node in post_order:
            preds = list(cfg.predecessors(node))
            new_dom = intersect(dom[p] for p in preds)
            new_dom.add(node)
            if dom[node] != new_dom:
                dom[node] = new_dom
                changed = True
        if not changed:
            break
    # for block in dom:
        # log_file.write(f"{block.label}: {[b.label for b in dom[block]]}\n")
    return dom

def rev_dom(dom: dict[cfg.BasicBlock, set[cfg.BasicBlock]]):
    """
    Given who is dominated by whom, return who dominates whom.
    """
    out = defaultdict(set)
    for block in dom:
        for dominated in dom[block]:
            out[dominated].add(block)
    return out

def get_dominance_frontier(cfg: nx.DiGraph, dom: dict[cfg.BasicBlock, set[cfg.BasicBlock]]):
    """
    Get the dominance frontier, given the dominance relation.
    """
    log_file.write("--- Getting dominance frontier ---")
    frontier = defaultdict(set)
    rev_dom_map = rev_dom(dom)
    for block in rev_dom_map:
        dominated_succs = set()
        for dominated in rev_dom_map[block]:
            dominated_succs.update(cfg.successors(dominated))
        frontier[block] = [b for b in dominated_succs if b not in rev_dom_map[block] or b == block]
    for block in frontier:
        log_file.write(f"{block.label}: {[b.label for b in frontier[block]]}\n")
    return frontier

def get_dom_tree(dom: dict[cfg.BasicBlock, set[cfg.BasicBlock]]):
    """
    Get the dominance tree, given the dominance relation.
    """
    log_file.write("--- Getting dominance tree ---")
    rev_dom_map = rev_dom(dom)
    dom_rev_strict = {a: {b for b in bs if b != a} for a, bs in rev_dom_map.items()} # dominated but not self
    # grandparent domination
    dom_rev_strict_2x = {a: set().union(*(dom_rev_strict[b] for b in bs)) for a, bs in dom_rev_strict.items()} 
    return {a: {b for b in bs if b not in dom_rev_strict_2x[a]} for a, bs in dom_rev_strict.items()}

def get_block_defs(blocks):
    """
    Get a map from variable names to defining blocks.
    """
    out = defaultdict(set)
    for name, block in blocks.items():
        for instr in block:
            if 'dest' in instr:
                out[instr['dest']].add(name)
    return dict(out)

def get_phis(cfg, df, defs):
    """
    Find where to insert phi-nodes in the blocks.
    """
    log_file.write(" --- Getting phis --- ")
    phis = {b: set() for b in cfg.nodes}
    for v, v_defs in defs.items():
        v_defs_list = list(v_defs)
        # print(f"Defining {v} in {[b for b in v_defs_list]}")
        for d in v_defs_list:
            for block in df[d]:
                if v not in phis[block]:
                    phis[block].add(v)
                    # print(f"Adding phi for {v} in {block.label}")
                    if block not in v_defs_list:
                        v_defs_list.append(block)
    for block in phis:
        log_file.write(f"{block.label}: {[v for v in phis[block]]}\n")
    return phis

def get_types(func):
    """
    Get the types of the variables in a function.
    """
    types = {arg['name']: arg['type'] for arg in func.get('args', [])}
    for instr in func['instrs']:
        if 'dest' in instr:
            types[instr['dest']] = instr['type']
    return types

def get_arg_names(func):
    """
    Get the names of the arguments to a function.
    """
    return {arg['name'] for arg in func.get('args', [])}

def ssa_rename(cfg, phis, dom_tree, arg_names, entry):
    stack = defaultdict(list, {v: [v] for v in arg_names})
    phi_args = {b: {p: [] for p in phis[b]} for b in cfg.nodes} # dict of dicts of lists
    phi_dests = {b: {p: None for p in phis[b]} for b in cfg.nodes} # dict of dicts of lists
    counters = defaultdict(int) # assign the next usable name per variable

    def _push_fresh(var):
        fresh = '{}.{}'.format(var, counters.get(var, 0))
        counters[var] += 1
        stack[var].insert(0, fresh)
        return fresh

    def _rename(block):
        log_file.write(f"Renaming block {block.label}\n")
        # Save stacks.
        old_stack = {k: list(v) for k, v in stack.items()}

        # Rename phi-node destinations.
        for p in phis[block]:
            phi_dests[block][p] = _push_fresh(p)

        for instr in block.instrs:
            log_file.write(f"Renaming {instr}\n")
            # Rename arguments in normal instructions.
            if 'args' in instr:
                new_args = [stack[arg][0] for arg in instr['args']]
                instr['args'] = new_args
                log_file.write(f"Renaming args for {instr['args']} in {block.label}\n")
            # Rename destinations.
            if 'dest' in instr:
                instr['dest'] = _push_fresh(instr['dest'])
                log_file.write(f"Renaming dest for {instr['dest']} in {block.label}\n")
        # Rename phi-node arguments (in successors).
        for s in cfg.successors(block):
            log_file.write(f"Renaming successors of {block.label}: {s.label}\n")
            for p in phis[s]:
                if stack.get(p):
                    phi_args[s][p].append((block, stack[p][0]))
                else:
                    # The variable is not defined on this path
                    phi_args[s][p].append((block, "__undefined"))

        # Recursive calls.
        for b in sorted(dom_tree[block]):
            _rename(b)

        # Restore stacks.
        stack.clear()
        stack.update(old_stack)

    _rename(entry)

    return phi_args, phi_dests

def insert_phis(cfg, phi_args, phi_dests, types):
    for block in cfg.nodes:
        if len(block.instrs) > 0:
            new_instrs = [block.instrs[0]]
            for dest, pairs in sorted(phi_args[block].items()):
                phi = {
                    'op': 'phi',
                    'dest': phi_dests[block][dest],
                    'type': types[dest],
                    'labels': [p[0].label for p in pairs],
                    'args': [p[1] for p in pairs],
                }
                new_instrs.append(phi)
                log_file.write(f"Inserting phi for {dest} in {block.label}\n")
            # Append the original instructions after the phi nodes
            new_instrs.extend(block.instrs[1:])
            # print(block.instrs)
            # print(new_instrs)
            # Replace the block's instructions with the new list
            block.instrs = new_instrs
            # print(block.instrs)
    
    # for block in cfg.nodes:
        # print(block.instrs)

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    log_file = open("log/ssa.log", "w")
    for fn in prog["functions"]:
        program_cfg, entry_block = cfg.construct_cfg(fn["instrs"])
        def_blocks = get_def_blocks(program_cfg)
        dom = get_dominators(program_cfg, entry_block)
        rev_dom_map = rev_dom(dom)
        log_file.write("Reverse dominance:\n")
        for block in rev_dom_map:
            log_file.write(f"{block.label}: {[b.label for b in rev_dom_map[block]]}\n")
        df = get_dominance_frontier(program_cfg, dom)
        phis = get_phis(program_cfg, df, def_blocks)
        types = get_types(fn)
        arg_names = get_arg_names(fn)
        dom_tree = get_dom_tree(dom)
        log_file.write("Dominance tree:\n")
        for block in dom_tree:
            log_file.write(f"{block.label}: {[b.label for b in dom_tree[block]]}\n")
        phi_args, phi_dests = ssa_rename(program_cfg, phis, dom_tree, arg_names, entry_block)
        insert_phis(program_cfg, phi_args, phi_dests, types)
        log_file.write("--- Program after SSA ---\n")
        for block in program_cfg.nodes:
            log_file.write(f"{block.label}: {block.instrs}\n")
        fn["instrs"] = cfg.cfg_to_instrs(program_cfg)
    json.dump(prog, sys.stdout, indent=2)
    log_file.close()