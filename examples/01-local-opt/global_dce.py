# Global Dead Code Elimination
import json
import sys

def all_used(instrs):
    used = set()
    for instr in instrs:
        if "args" in instr:
            for arg in instr["args"]:
                used.add(arg)
    return used

def mark_unused(instrs, used):
    for instr in instrs:
        if "dest" in instr:
            if instr["dest"] not in used:
                instr["op"] = "nop"
                log_file.write(f"Marked {instr['dest']} as unused\n")
    return instrs

def should_keep(instr):
    if "op" not in instr:
        return True
    return instr["op"] != "nop"

def remove_nops(instrs):
    return [instr for instr in instrs if should_keep(instr)]

if __name__ == "__main__":
    log_file = open("log/global_dce.log", "w")
    prog = json.load(sys.stdin)
    log_file.write(f"Processing {len(prog['functions'])} function(s)\n")
    for fn in prog["functions"]:
        log_file.write(f"--> Processing function {fn['name']} -->\n")
        used = all_used(fn["instrs"])
        fn["instrs"] = mark_unused(fn["instrs"], used)
        fn["instrs"] = remove_nops(fn["instrs"])
    json.dump(prog, sys.stdout, indent=2)