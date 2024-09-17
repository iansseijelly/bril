# Local Value Numbering
import json
import sys
import cfg
from collections import OrderedDict

def reverse_lookup(dict, value):
    for k, v in dict.items():
        if v == value:
            return k
    return None

def lvn(block):
    # key: dst, value: op, args
    lvn_blob_map = OrderedDict()
    # first pass: collect all the args, populate lvn dictionary
    # mark common subexprs as ids
    for insn in block.instrs:
        args = []
        if "args" in insn:
            # collect all args
            for i, arg in enumerate(insn["args"]):
                original_arg = arg
                while arg in lvn_blob_map and lvn_blob_map[arg][0] == "id":
                    arg = lvn_blob_map[arg][1][0]
                
                if arg != original_arg:
                    log_file.write(f"Found an arg common_subexpr: {original_arg} -> {arg}\n")
                    insn["args"][i] = arg

                args.append(arg)
                
                if arg not in lvn_blob_map:
                    lvn_blob_map[arg] = ("uninferable", None)
                    log_file.write(f"found uninferable: {arg}\n")
        # look up this common subexpr
        if "dest" in insn:
            subexpr = (insn["op"], args)
            log_file.write(f"Subexpr: {subexpr}\n")
            if insn["op"] == "const" or insn["op"] == "id" or subexpr not in lvn_blob_map.values():
                lvn_blob_map[insn["dest"]] = subexpr
            else:
                # reverse lookup
                key = reverse_lookup(lvn_blob_map, subexpr)
                log_file.write(f"Found a match: {subexpr}\n")
                lvn_blob_map[insn["dest"]] = ("id", [key])
                insn.update({
                    "op": "id",
                    "args": [key]
                })
        log_file.write(f"insn: {insn}\n")

if __name__ == "__main__":
    log_file = open("log/lvn.log", "w")
    prog = json.load(sys.stdin)
    log_file.write(f"Processing {len(prog['functions'])} function(s)\n")
    for fn in prog["functions"]:
        log_file.write(f"--> Processing function {fn['name']} -->\n")
        local_cfg = cfg.construct_cfg(fn["instrs"])
        for block in local_cfg.nodes:
            lvn(block)
        fn["instrs"] = cfg.cfg_to_instrs(local_cfg)
    json.dump(prog, sys.stdout, indent=2)
                    