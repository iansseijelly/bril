# Basic Block Dead Code Elimination
import json
import sys
import cfg
from collections import OrderedDict

def local_dce(block):
    unused = OrderedDict()
    for insn in block.instrs:
        if "args" in insn:
            for arg in insn["args"]:
                if arg in unused:
                    unused.pop(arg)
        if "dest" in insn:
            if insn["dest"] in unused:
                # prune the instruction
                unused_insn = unused[insn["dest"]]
                unused_insn["op"] = "nop"
            unused[insn["dest"]] = insn
    
    i = 0
    while i < len(block.instrs):
        insn = block.instrs[i]
        if "op" in insn and insn["op"] == "nop":
            block.instrs.remove(insn)
            log_file.write(f"Pruned {insn}\n")
        else:
            i += 1
                

if __name__ == "__main__":
    log_file = open("log/local_dce.log", "w")
    prog = json.load(sys.stdin)
    log_file.write(f"Processing {len(prog['functions'])} function(s)\n")
    for fn in prog["functions"]:
        log_file.write(f"--> Processing function {fn['name']} -->\n")
        local_cfg = cfg.construct_cfg(fn["instrs"])
        for block in local_cfg.nodes:
            local_dce(block)
        fn["instrs"] = cfg.cfg_to_instrs(local_cfg)
    json.dump(prog, sys.stdout, indent=2)
