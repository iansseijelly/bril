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
    for insn in block.instrs:
        args = []
        if "args" in insn:
            # collect all args
            for arg in insn["args"]:
                if arg in lvn_blob_map.keys():
                    args.append(arg)
                else:
                    lvn_blob_map[arg] = ("uninferable", None) 

                    args.append(arg)
        # look up this common subexpr
        if "dest" in insn:
            subexpr = (insn["op"], args)
            if insn["op"] == "const" or subexpr not in lvn_blob_map.values():
                lvn_blob_map[insn["dest"]] = subexpr
            else:
                # reverse lookup
                key = reverse_lookup(lvn_blob_map, subexpr)
                log_file.write(f"Found a match: {subexpr}\n")
                insn.update({
                    "op": "id",
                    "args": [key]
                })
                lvn_blob_map[insn["dest"]] = ("id", [key])

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
                    